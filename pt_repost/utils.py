import functools
import hashlib
import json
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Hashable
from datetime import timedelta
from pathlib import Path
from shutil import which
from typing import Any, TypeVar

import orjson
from bencode2 import bdecode, bencode
from pydantic import TypeAdapter
from sslog import logger


def run_command(
    command: list[str],
    cwd: str | Path | None = None,
    check: bool = False,
    stdout: int | None = None,
    stderr: int | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    logger.debug("executing command {!r}", shlex.join(command))
    return subprocess.run(command, **kwargs, cwd=cwd, stdout=stdout, stderr=stderr, check=check)


def must_run_command(
    executable: str,
    command: list[str],
    cwd: str | Path | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    cmd = which(executable)
    if cmd is None:
        logger.fatal("can't find {!r}", executable)
        sys.exit(1)
    logger.trace("executing command {!r}", shlex.join([cmd, *command]))
    return subprocess.run([cmd, *command], **kwargs, cwd=cwd)


def get_video_duration(video_file: Path) -> int:
    p = must_run_command(
        "ffprobe",
        [
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            str(video_file),
        ],
        capture_output=True,
        check=False,
    )
    if p.returncode:
        print(p.stdout)
        print(p.stderr)
        raise Exception("failed to get video info")

    probe = json.loads(p.stdout)

    return int(json.loads(probe["format"]["duration"]))


# 10mb
IMAGE_SIZE_LIMIT = 10 * 1024 * 1024


oxipng_executable = which("oxipng")
pngquant_executable = which("pngquant")


def must_find_executable(e: str) -> str:
    tool = which(e)
    if tool is None:
        raise Exception("can't find ffmpeg")
    return tool


ffmpeg: str = must_find_executable("ffmpeg")


def generate_images(
    video_file: Path,
    tmpdir: Path,
    image_format: str = "png",
    count: int = 3,
) -> list[Path]:
    temp = tmpdir.joinpath("images")
    temp.mkdir(exist_ok=True, parents=True)
    results = []
    duration = get_video_duration(video_file)

    # long enough
    if duration > 30 * 60:
        start = 10 * 60
        step = (duration - start * 2) // count
    else:
        start = 30
        step = (duration - 60) // count

    total = 0

    for i in range(count):
        seek = start + step * i - 5
        j = -1
        while True:
            j += 1
            seek = seek + 5
            logger.info("screenshot from {} at {}", video_file.name, timedelta(seconds=seek))
            raw_image_file = temp.joinpath(f"{i}.{j}.raw.{image_format}")
            run_command(
                [
                    ffmpeg,
                    "-y",
                    "-ss",
                    str(seek),
                    "-i",
                    str(video_file),
                    "-update",
                    "1",
                    "-loglevel",
                    "debug",
                    "-frames:v",
                    "1",
                    # "-compression_level",
                    # "50",
                    str(raw_image_file),
                ],
                stdout=subprocess.DEVNULL,
                # stderr=subprocess.DEVNULL,
                check=True,
            )

            if raw_image_file.lstat().st_size <= IMAGE_SIZE_LIMIT:
                results.append(raw_image_file)
                break

            file: Path = raw_image_file

            if image_format == "png":
                logger.warning(
                    "image too large {}",
                    human_readable_size(raw_image_file.lstat().st_size),
                )

                file = raw_image_file.with_name(f"{i}.{j}.{image_format}")

                if oxipng_executable is not None:
                    logger.info("try lossless compression")
                    file.write_bytes(raw_image_file.read_bytes())
                    run_command(
                        [
                            oxipng_executable,
                            "-o",
                            "max",
                            "--strip",
                            "all",
                            "--alpha",
                            str(file),
                        ],
                        stdout=subprocess.DEVNULL,
                    )

                    logger.info("result {}", human_readable_size(file.lstat().st_size))

                if file.lstat().st_size >= IMAGE_SIZE_LIMIT:
                    logger.warning(
                        "png is still too large {}",
                        human_readable_size(file.lstat().st_size),
                    )
                    if pngquant_executable is not None:
                        logger.info("try non-lossless compression")
                        file.unlink(missing_ok=True)
                        run_command(
                            [
                                pngquant_executable,
                                "-f",
                                "--skip-if-larger",
                                "--quality=90-100",
                                "--strip",
                                "--output",
                                str(file),
                                "--",
                                str(raw_image_file),
                            ],
                            stdout=subprocess.DEVNULL,
                        )
                        logger.info("result {}", human_readable_size(file.lstat().st_size))

            total += 1
            logger.info("currently generate {} screenshot, {} is ok", total, i + 1)
            size = file.lstat().st_size
            if size >= IMAGE_SIZE_LIMIT:
                logger.warning("image too large {}", human_readable_size(size))
                continue

            results.append(file)
            break

    return results


def human_readable_size(size: float, decimal_places: int = 2) -> str:
    for unit in ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]:
        if size < 1024.0 or unit == "PiB":
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


_T = TypeVar("_T")


@functools.cache
def get_type_adapter(t: type[_T]) -> TypeAdapter[_T]:
    return TypeAdapter(t)


_K = TypeVar("_K")


def parse_obj_as(typ: type[_K], value: Any, *, strict: bool | None = None) -> _K:
    t: TypeAdapter[_K] = get_type_adapter(typ)  # type: ignore[arg-type]
    return t.validate_python(value, strict=strict)


def parse_json_as(typ: type[_K], value: str | bytes, *, strict: bool | None = None) -> _K:
    t: TypeAdapter[_K] = get_type_adapter(typ)  # type: ignore[arg-type]
    return t.validate_python(orjson.loads(value), strict=strict)


def get_info_hash_v1_from_content(content: bytes) -> str:
    data = bdecode(content)
    enc = bencode(data[b"info"])
    return hashlib.sha1(enc).hexdigest()


_J = TypeVar("_J", bound=Hashable)


def dedupe(seq: list[_J]) -> list[_J]:
    seen: set[_J] = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


def an2cn(i: int) -> str:
    match i:
        case 1:
            return "一"
        case 2:
            return "二"
        case 3:
            return "三"
        case 4:
            return "四"
        case 5:
            return "五"
        case 6:
            return "六"
        case 7:
            return "七"
        case 8:
            return "八"
        case 9:
            return "九"
        case 10:
            return "十"

    if i >= 100:
        raise NotImplementedError(f"an2cn({i!r})")

    if i < 20:
        return "十" + an2cn(i // 10)

    if i % 10 == 0:
        return an2cn(i // 10) + "十"

    return an2cn(i // 10) + "十" + an2cn(i % 10)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="pt-repost") as d:
        generate_images(Path(sys.argv[1]), Path(d))
