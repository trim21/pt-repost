import dataclasses
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from shutil import which
from typing import List, Optional

import rich
from pydantic import Field, TypeAdapter
from sslog import logger

from app.utils import run_command, parse_obj_as


@dataclasses.dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class Track:
    # type: str = Field(alias="@type")
    # unique_id: str = Field(alias="UniqueID")
    hdr_format: str = Field("", alias="HDR_Format")
    hdr_format_string: str = Field("", alias="HDR_Format_String")
    video_count: Optional[str] = Field(None, alias="VideoCount")
    audio_count: Optional[str] = Field(None, alias="AudioCount")
    text_count: Optional[str] = Field(None, alias="TextCount")
    file_extension: Optional[str] = Field(None, alias="FileExtension")
    format: str = Field(alias="Format")
    # format__version: Optional[str] = Field(None, alias="Format_Version")
    # file_size: Optional[str] = Field(None, alias="FileSize")
    # duration: str | None = Field(None, alias="Duration")
    # overall_bit_rate: Optional[str] = Field(None, alias="OverallBitRate")
    # frame_rate: str | None = Field(None, alias="FrameRate")
    # frame_count: str = Field("", alias="FrameCount")
    # stream_size: str | None = Field(None, alias="StreamSize")
    # is_streamable: Optional[str] = Field(None, alias="IsStreamable")
    # file__modified__date: Optional[str] = Field(None, alias="File_Modified_Date")
    # file__modified__date__local: Optional[str] = Field(
    #     None, alias="File_Modified_Date_Local"
    # )
    # encoded__application: Optional[str] = Field(None, alias="Encoded_Application")
    # encoded__library: Optional[str] = Field(None, alias="Encoded_Library")
    # stream_order: Optional[str] = Field(None, alias="StreamOrder")
    # id: Optional[str] = Field(None, alias="ID")
    # format__profile: Optional[str] = Field(None, alias="Format_Profile")
    # format__level: Optional[str] = Field(None, alias="Format_Level")
    # format__tier: Optional[str] = Field(None, alias="Format_Tier")
    # codec_id: Optional[str] = Field(None, alias="CodecID")
    # bit_rate: Optional[str] = Field(None, alias="BitRate")
    width: int = Field(alias="Width")
    height: int = Field(alias="Height")
    # sampled__width: Optional[str] = Field(None, alias="Sampled_Width")
    # sampled__height: Optional[str] = Field(None, alias="Sampled_Height")
    # pixel_aspect_ratio: Optional[str] = Field(None, alias="PixelAspectRatio")
    # display_aspect_ratio: Optional[str] = Field(None, alias="DisplayAspectRatio")
    # frame_rate__mode: Optional[str] = Field(None, alias="FrameRate_Mode")
    # frame_rate__num: Optional[str] = Field(None, alias="FrameRate_Num")
    # frame_rate__den: Optional[str] = Field(None, alias="FrameRate_Den")
    # color_space: Optional[str] = Field(None, alias="ColorSpace")
    # chroma_subsampling: Optional[str] = Field(None, alias="ChromaSubsampling")
    # bit_depth: Optional[str] = Field(None, alias="BitDepth")
    # delay: Optional[str] = Field(None, alias="Delay")
    # delay__source: Optional[str] = Field(None, alias="Delay_Source")
    # default: Optional[str] = Field(None, alias="Default")
    # forced: Optional[str] = Field(None, alias="Forced")
    # colour_description_present: Optional[str] = None
    # colour_description_present__source: Optional[str] = Field(
    #     None, alias="colour_description_present_Source"
    # )
    # colour_range: Optional[str] = None
    # colour_range__source: Optional[str] = Field(None, alias="colour_range_Source")
    # colour_primaries: Optional[str] = None
    # colour_primaries__source: Optional[str] = Field(
    #     None, alias="colour_primaries_Source"
    # )
    # transfer_characteristics: Optional[str] = None
    # transfer_characteristics__source: Optional[str] = Field(
    #     None, alias="transfer_characteristics_Source"
    # )
    # matrix_coefficients: Optional[str] = None
    # matrix_coefficients__source: Optional[str] = Field(
    #     None, alias="matrix_coefficients_Source"
    # )
    # format__commercial__if_any: Optional[str] = Field(
    #     None, alias="Format_Commercial_IfAny"
    # )
    # format__settings__endianness: Optional[str] = Field(
    #     None, alias="Format_Settings_Endianness"
    # )
    # bit_rate__mode: Optional[str] = Field(None, alias="BitRate_Mode")
    # channels: Optional[str] = Field(None, alias="Channels")
    # channel_positions: Optional[str] = Field(None, alias="ChannelPositions")
    # channel_layout: Optional[str] = Field(None, alias="ChannelLayout")
    # samples_per_frame: Optional[str] = Field(None, alias="SamplesPerFrame")
    # sampling_rate: Optional[str] = Field(None, alias="SamplingRate")
    # sampling_count: Optional[str] = Field(None, alias="SamplingCount")
    # compression__mode: Optional[str] = Field(None, alias="Compression_Mode")
    # video__delay: Optional[str] = Field(None, alias="Video_Delay")
    # language: Optional[str] = Field(None, alias="Language")
    # service_kind: Optional[str] = Field(None, alias="ServiceKind")
    # extra: Optional[Extra] = None
    # type_order: Optional[str] = Field(None, alias="@typeorder")
    # element_count: Optional[str] = Field(None, alias="ElementCount")
    # title: Optional[str] = Field(None, alias="Title")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Audio:
    format: str = Field(..., alias="Format")
    # count: str = Field(..., alias="Count")
    # stream_count: str = Field(..., alias="StreamCount")
    # stream_kind: str = Field(..., alias="StreamKind")
    # stream_kind__string: str = Field(..., alias="StreamKind_String")
    # stream_kind_id: str = Field(..., alias="StreamKindID")
    # stream_order: str = Field(..., alias="StreamOrder")
    # id: str = Field(..., alias="ID")
    # id__string: str = Field(..., alias="ID_String")
    # unique_id: str = Field(..., alias="UniqueID")
    # format__string: str = Field(..., alias="Format_String")
    # format__info: str = Field(..., alias="Format_Info")
    # format__url: str = Field(..., alias="Format_Url")
    # format__commercial: str = Field(..., alias="Format_Commercial")
    # format__commercial__if_any: str = Field(..., alias="Format_Commercial_IfAny")
    # format__settings__endianness: str = Field(..., alias="Format_Settings_Endianness")
    # format__additional_features: str = Field(..., alias="Format_AdditionalFeatures")
    # internet_media_type: str = Field(..., alias="InternetMediaType")
    # codec_id: str = Field(..., alias="CodecID")
    # duration: str = Field(..., alias="Duration")
    # duration__string: str = Field(..., alias="Duration_String")
    # duration__string1: str = Field(..., alias="Duration_String1")
    # duration__string2: str = Field(..., alias="Duration_String2")
    # duration__string3: str = Field(..., alias="Duration_String3")
    # duration__string5: str = Field(..., alias="Duration_String5")
    # bit_rate__mode: str = Field(..., alias="BitRate_Mode")
    # bit_rate__mode__string: str = Field(..., alias="BitRate_Mode_String")
    # bit_rate: str = Field(..., alias="BitRate")
    # bit_rate__string: str = Field(..., alias="BitRate_String")
    # channels: str = Field(..., alias="Channels")
    # channels__string: str = Field(..., alias="Channels_String")
    # channel_positions: str = Field(..., alias="ChannelPositions")
    # channel_positions__string2: str = Field(..., alias="ChannelPositions_String2")
    # channel_layout: str = Field(..., alias="ChannelLayout")
    # samples_per_frame: str = Field(..., alias="SamplesPerFrame")
    # sampling_rate: str = Field(..., alias="SamplingRate")
    # sampling_rate__string: str = Field(..., alias="SamplingRate_String")
    # sampling_count: str = Field(..., alias="SamplingCount")
    # frame_rate: str = Field(..., alias="FrameRate")
    # frame_rate__string: str = Field(..., alias="FrameRate_String")
    # compression__mode: str = Field(..., alias="Compression_Mode")
    # compression__mode__string: str = Field(..., alias="Compression_Mode_String")
    # delay: str = Field(..., alias="Delay")
    # delay__string3: str = Field(..., alias="Delay_String3")
    # delay__string5: str = Field(..., alias="Delay_String5")
    # delay__source: str = Field(..., alias="Delay_Source")
    # delay__source__string: str = Field(..., alias="Delay_Source_String")
    # video__delay: str = Field(..., alias="Video_Delay")
    # video__delay__string3: str = Field(..., alias="Video_Delay_String3")
    # video__delay__string5: str = Field(..., alias="Video_Delay_String5")
    # stream_size: str = Field(..., alias="StreamSize")
    # stream_size__string: str = Field(..., alias="StreamSize_String")
    # stream_size__string1: str = Field(..., alias="StreamSize_String1")
    # stream_size__string2: str = Field(..., alias="StreamSize_String2")
    # stream_size__string3: str = Field(..., alias="StreamSize_String3")
    # stream_size__string4: str = Field(..., alias="StreamSize_String4")
    # stream_size__string5: str = Field(..., alias="StreamSize_String5")
    # stream_size__proportion: str = Field(..., alias="StreamSize_Proportion")
    # language: str = Field(..., alias="Language")
    # language__string: str = Field(..., alias="Language_String")
    # language__string1: str = Field(..., alias="Language_String1")
    # language__string2: str = Field(..., alias="Language_String2")
    # language__string3: str = Field(..., alias="Language_String3")
    # language__string4: str = Field(..., alias="Language_String4")
    # service_kind: str = Field(..., alias="ServiceKind")
    # service_kind__string: str = Field(..., alias="ServiceKind_String")
    # default: str = Field(..., alias="Default")
    # default__string: str = Field(..., alias="Default_String")
    # forced: str = Field(..., alias="Forced")
    # forced__string: str = Field(..., alias="Forced_String")
    # extra: Extra


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Text:
    title: str = Field("", alias="Title")
    language: str = Field("", alias="Language")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Media:
    ref: str = Field(alias="@ref")
    track: List[Track]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class MediaInfo:
    # creating_library: CreatingLibrary = Field(alias="creatingLibrary")

    video: list[Track] = Field(default_factory=list)
    audio: list[Audio] = Field(default_factory=list)
    text: list[Text] = Field(default_factory=list)


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
