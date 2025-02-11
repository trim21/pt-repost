import dataclasses
import os
import pathlib
import re
import sys
import uuid
from pathlib import Path
from typing import Annotated, Any

import durationpy
import orjson
import tomli
import yaml
import yarl
from pydantic import BeforeValidator, ByteSize, Field, HttpUrl

from pt_repost.utils import parse_obj_as


@dataclasses.dataclass(frozen=True, slots=True)
class SSD:
    passkey: str
    cookies: str = ""
    api_token: str = ""

    def __post_init__(self) -> None:
        if self.api_token:
            return
        if self.cookies:
            return
        raise ValueError("must set ssd api-token or cookies")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Website:
    ssd: SSD


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class RSS:
    url: str
    includes: list[re.Pattern[str]] = dataclasses.field(default_factory=list)
    excludes: list[re.Pattern[str]] = dataclasses.field(default_factory=list)


def parse_go_duration_str(s: Any) -> Any:
    if isinstance(s, float | int):
        return int(s)

    if isinstance(s, str):
        return int(durationpy.from_str(s).total_seconds())

    return s


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Rss:
    url: str
    exclude_url: str = ""
    website: str
    includes: Annotated[list[str | list[str]], Field(default_factory=list)]
    excludes: Annotated[list[str | list[str]], Field(default_factory=list)]
    interval: Annotated[int, Field(60 * 30), BeforeValidator(parse_go_duration_str)]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Image:
    cmct_api_token: str = ""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Config:
    debug: bool = False
    node_id: Annotated[str, Field(alias="node-id", min_length=1)] = os.getenv(
        "PT_REPOST_NODE_ID"
    ) or hex(uuid.getnode())

    target_website: Annotated[str, Field(alias="target-website")]

    images: Image
    website: Website
    rss: Annotated[list[Rss], Field(default_factory=list)]

    http_proxy: Annotated[
        str | None,
        BeforeValidator(lambda x: x or None),  # filter empty string
    ] = None

    max_processing_size: Annotated[ByteSize, Field("100GiB", alias="max-processing-size")]
    max_single_torrent_size: Annotated[ByteSize, Field("100GiB", alias="max-single-torrent-size")]
    max_processing_per_node: Annotated[int, Field(100000, alias="max-processing-per-node")]
    recent_release_seconds: Annotated[
        int, Field(0, alias="recent-release"), BeforeValidator(parse_go_duration_str)
    ]

    min_seeding_seconds: Annotated[
        int,
        Field(0, alias="min-seeding-seconds"),
        BeforeValidator(parse_go_duration_str),
    ] = 0

    # rss: list[RSS]
    pg_host: str
    pg_port: int
    pg_user: str | None = None
    pg_password: str | None = None

    data_dir: Annotated[pathlib.Path, Field("", alias="data-dir")]
    tmdb_api_token: Annotated[str, Field(alias="tmdb-api-token")]
    db_path: Path = Path(os.getcwd(), "data.db")
    qb_url: Annotated[HttpUrl, Field(alias="qb-url")]
    qb_backup_dir: Annotated[str, Field("", alias="qb-backup-dir")]

    includes: Annotated[list[re.Pattern[str]], Field(default_factory=list)]
    excludes: Annotated[list[re.Pattern[str]], Field(default_factory=list)]

    def pg_dsn(self) -> str:
        return str(
            yarl.URL.build(
                scheme="postgresql",
                user=self.pg_user,
                password=self.pg_password,
                host=self.pg_host,
                port=self.pg_port,
            )
        )


def load_config(config_file: str | Path | None = None) -> Config:
    p = Path(config_file or Path(__file__, "../../config.toml").resolve())

    if not p.exists():
        print("please put a config.toml at {}".format(p))
        sys.exit(1)

    if p.suffix.lower() == ".yaml":
        config = parse_obj_as(Config, yaml.safe_load(p.read_text(encoding="utf-8")))
    elif p.suffix.lower() == ".toml":
        config = parse_obj_as(Config, tomli.loads(p.read_text(encoding="utf-8")))
    elif p.suffix.lower() == ".json":
        config = parse_obj_as(Config, orjson.loads(p.read_bytes()))
    else:
        raise Exception("not supported config format, only support yaml/toml/json")

    data_dir = config.data_dir.expanduser()

    if not data_dir.is_absolute():
        data_dir = p.parent.joinpath(data_dir)

    return dataclasses.replace(config, data_dir=data_dir)


video_ext = (".mkv", ".mp4", ".ts")
