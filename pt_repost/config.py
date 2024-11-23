import dataclasses
import os
import sys
from pathlib import Path
from typing import Annotated

import tomli
from pydantic import Field, HttpUrl, TypeAdapter


@dataclasses.dataclass(frozen=True, slots=True)
class SSD:
    cookies: str = ""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Website:
    ssd: SSD


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Config:
    website: Website
    http_proxy: str | None = None
    db_path: Path = Path(Path(os.getcwd(), "data.db"))
    qb_url: Annotated[HttpUrl, Field(alias="qb-url")]
    qb_backup_dir: Annotated[str, Field("", alias="qb-backup-dir")]


def load_config():
    config_file = Path(os.getcwd(), "config.toml")

    if not config_file.exists():
        print("please put a config.toml at {}".format(config_file))
        sys.exit(1)

    config: Config = TypeAdapter(Config).validate_python(
        tomli.loads(config_file.read_text())
    )

    return config


video_ext = {".mkv", ".mp4", ".ts"}
