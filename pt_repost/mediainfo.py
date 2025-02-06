import dataclasses
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated, List, Optional

import orjson
from pydantic import Field
from sslog import logger

from pt_repost.utils import must_find_executable, must_run_command, parse_obj_as


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Track:
    hdr_format: Annotated[str, Field("", alias="HDR_Format")]
    hdr_format_string: Annotated[str, Field("", alias="HDR_Format_String")]
    hdr_format_compatibility: Annotated[str, Field("", alias="HDR_Format_Compatibility")]
    video_count: Annotated[Optional[str], Field(None, alias="VideoCount")]
    audio_count: Annotated[Optional[str], Field(None, alias="AudioCount")]
    text_count: Annotated[Optional[str], Field(None, alias="TextCount")]
    file_extension: Annotated[Optional[str], Field(None, alias="FileExtension")]
    format: Annotated[str, Field(alias="Format")]

    width: Annotated[int, Field(alias="Width")]
    height: Annotated[int, Field(alias="Height")]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Audio:
    format: str = Field(alias="Format")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Text:
    title: str = Field("", alias="Title")
    language: str = Field("", alias="Language")
    language_string: str = Field("Language_String", alias="Language_String")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Media:
    ref: str = Field(alias="@ref")
    track: List[Track]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class MediaInfo:
    video: Annotated[list[Track], Field(default_factory=list)]
    audio: Annotated[list[Audio], Field(default_factory=list)]
    text: Annotated[list[Text], Field(default_factory=list)]


def parse_mediainfo_json(s: str) -> MediaInfo:
    obj = json.loads(s)

    if not obj["media"]:
        raise ValueError("failed to get mediainfo, please report this issue")

    videos = [s for s in obj["media"]["track"] if s["@type"] == "Video"]
    audio = [s for s in obj["media"]["track"] if s["@type"] == "Audio"]
    text = [s for s in obj["media"]["track"] if s["@type"] == "Text"]

    return parse_obj_as(MediaInfo, {"video": videos, "audio": audio, "text": text})


mediainfo = must_find_executable("mediainfo")
logger.info("using mediainfo at {!r}", mediainfo)


def extract_mediainfo_from_file(file: Path) -> tuple[str, str]:
    with tempfile.TemporaryDirectory(prefix="pt-repost-") as tempdir:
        out_file = Path(tempdir, "mediainfo.txt")
        must_run_command(
            mediainfo,
            [f"--LogFile={out_file}", file.name],
            cwd=str(file.parent),
            stdout=subprocess.DEVNULL,
        )

        json_file = Path(tempdir, "mediainfo.json")
        must_run_command(
            mediainfo,
            [f"--LogFile={json_file}", "--output=JSON", file.name],
            cwd=str(file.parent),
            stdout=subprocess.DEVNULL,
        )

        return (
            out_file.read_text("utf-8"),
            orjson.dumps(
                orjson.loads(json_file.read_text("utf-8")),
                option=orjson.OPT_INDENT_2,
            ).decode(),
        )
