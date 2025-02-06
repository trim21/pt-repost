import dataclasses
import os
import pathlib
import re
import sys
import uuid
from pathlib import Path
from typing import Annotated

import durationpy
import tomli
import yarl
from pydantic import BeforeValidator, ByteSize, Field, HttpUrl, TypeAdapter


@dataclasses.dataclass(frozen=True, slots=True)
class SSD:
    passkey: str
    cookies: str = ""
    api_token: str = ""

    def __post_init__(self):
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


def _regex_ignore_case(s: str) -> re.Pattern[str]:
    return re.compile(s, flags=re.IGNORECASE | re.UNICODE)


def parse_go_duration_str(s: str) -> int:
    if isinstance(s, float | int):
        return int(s)

    if not isinstance(s, str):
        raise ValueError("duration must be str/int/float")

    return int(durationpy.from_str(s).total_seconds())


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
        int, Field(3600, alias="recent-release"), BeforeValidator(parse_go_duration_str)
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

    data_dir: Annotated[pathlib.Path, Field(alias="data-dir")]
    tmdb_api_token: Annotated[str, Field(alias="tmdb-api-token")]
    db_path: Path = Path(os.getcwd(), "data.db")
    qb_url: Annotated[HttpUrl, Field(alias="qb-url")]
    qb_backup_dir: Annotated[str, Field("", alias="qb-backup-dir")]

    includes: Annotated[list[re.Pattern[str]], Field(default_factory=list)]
    excludes: Annotated[list[re.Pattern[str]], Field(default_factory=list)]

    def pg_dsn(self) -> str:
        _ssl_root_cert = self.data_dir.joinpath("pt-repost-ca.crt")
        _ssl_cert = self.data_dir.joinpath("client.crt")
        ssl_key = self.data_dir.joinpath("client.key")

        # TODO: generate client key from ca

        if ssl_key.exists():
            os.chmod(ssl_key, 0o0600)

        return str(
            yarl.URL.build(
                scheme="postgresql",
                user=self.pg_user,
                password=self.pg_password,
                host=self.pg_host,
                port=self.pg_port,
                # query={
                #     "sslmode": "verify-ca",
                #     "sslrootcert": str(ssl_root_cert),
                #     "sslcert": str(ssl_cert),
                #     "sslkey": str(ssl_key),
                # },
            )
        )


def load_config(config_file: str | Path | None = None) -> Config:
    p = Path(config_file or Path(__file__, "../../config.toml").resolve())

    if not p.exists():
        print("please put a config.toml at {}".format(p))
        sys.exit(1)

    config: Config = TypeAdapter(Config).validate_python(tomli.loads(p.read_text()))

    data_dir = config.data_dir.expanduser()

    if not data_dir.is_absolute():
        data_dir = p.parent.joinpath(data_dir)

    return dataclasses.replace(config, data_dir=data_dir)


video_ext = (".mkv", ".mp4", ".ts")
