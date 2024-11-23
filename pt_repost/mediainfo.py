import dataclasses
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from shutil import which
from typing import Annotated, List, Optional

from pydantic import Field
from sslog import logger

from pt_repost.utils import parse_obj_as, run_command


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Track:
    hdr_format: str = Field("", alias="HDR_Format")
    hdr_format_string: str = Field("", alias="HDR_Format_String")
    video_count: Optional[str] = Field(None, alias="VideoCount")
    audio_count: Optional[str] = Field(None, alias="AudioCount")
    text_count: Optional[str] = Field(None, alias="TextCount")
    file_extension: Optional[str] = Field(None, alias="FileExtension")
    format: str = Field(alias="Format")

    width: int = Field(alias="Width")
    height: int = Field(alias="Height")


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

    videos = [s for s in obj["media"]["track"] if s["@type"] == "Video"]
    audio = [s for s in obj["media"]["track"] if s["@type"] == "Audio"]
    text = [s for s in obj["media"]["track"] if s["@type"] == "Text"]

    return parse_obj_as(MediaInfo, {"video": videos, "audio": audio, "text": text})


def extract_mediainfo_from_file(file: Path) -> tuple[str, str]:
    mediainfo = which("mediainfo")
    if not mediainfo:
        logger.fatal("failed to find mediainfo")
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="pt-repost-") as tempdir:
        out_file = Path(tempdir, "mediainfo.txt")
        run_command(
            [mediainfo, f"--LogFile={out_file}", str(file)],
            stdout=subprocess.DEVNULL,
        )

        json_file = Path(tempdir, "mediainfo.json")
        run_command(
            [mediainfo, f"--LogFile={json_file}", "--output=JSON", str(file)],
            stdout=subprocess.DEVNULL,
        )

        return out_file.read_text("utf-8"), json_file.read_text("utf-8")
