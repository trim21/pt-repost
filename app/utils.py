import json
import shlex
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from shutil import which

from sslog import logger


def run_command(
    command: list[str],
    cwd: str | None = None,
    check: bool = False,
    stdout: int | None = None,
    stderr: int | None = None,
    **kwargs,
):
    logger.trace("executing command {!r}", shlex.join(command))
    return subprocess.run(
        command, **kwargs, cwd=cwd, stdout=stdout, stderr=stderr, check=check
    )


def must_run_command(executable: str, command: list[str], cwd=None, **kwargs):
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


IMAGE_SIZE_LIMIT = 10 * 1024 * 1024


oxipng_executable = which("oxipng")
pngquant_executable = which("pngquant")


def generate_images(
    video_file: Path,
    tmpdir: Path,
    image_format="png",
    count=3,
) -> list[Path]:
    temp = tmpdir.joinpath("images")
    temp.mkdir(exist_ok=True, parents=True)
    results = []
    duration = get_video_duration(video_file)

    # long enough
    if duration > 60 * 30:
        start = 5 * 60
        step = (duration - start * 2) // count
    else:
        start = 30
        step = (duration - 60) // count

    total = 0

    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        logger.fatal("can't find ffmpeg")
        sys.exit(1)

    for i in range(count):
        seek = start + step * i - 5
        j = -1
        while True:
            j += 1
            seek = seek + 5
            logger.info(
                "screenshot from {} at {}", video_file.name, timedelta(seconds=seek)
            )
            file = temp.joinpath(f"{i}.{j}.png")
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
                    "-frames:v",
                    "1",
                    # "-compression_level",
                    # "50",
                    str(file),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            if file.lstat().st_size >= IMAGE_SIZE_LIMIT:
                if oxipng_executable is not None:
                    run_command(
                        [
                            oxipng_executable,
                            "-o",
                            "max",
                            "--strip",
                            "all",
                            "--alpha",
                            str(file),
                        ]
                    )
                elif pngquant_executable is not None:
                    run_command(
                        [pngquant_executable, "--quality=80-100", "--", str(file)]
                    )

            total += 1
            logger.info("currently generate {} screenshot, {} is ok", total, i + 1)
            size = file.lstat().st_size
            if size >= IMAGE_SIZE_LIMIT:
                logger.warning("png too large {}", human_readable_size(size))
                continue
            results.append(file)
            break
    return results


def human_readable_size(size, decimal_places=2):
    for unit in ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]:
        if size < 1024.0 or unit == "PiB":
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"
