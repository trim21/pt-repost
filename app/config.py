import dataclasses
import importlib.resources
import os
import sys
from pathlib import Path
from typing import Annotated

import tomli
from pydantic import Field, TypeAdapter

video_ext = {".mkv", ".mp4", ".ts"}


def get_source_text(file: str) -> str:
    return importlib.resources.files("app").joinpath(file).read_text("utf-8")


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
    db_path: Path = Path(
        os.environ.get("SQLITE_DB_FILE") or Path(os.getcwd(), "data.db")
    )
    qb_url: Annotated[str, Field(alias="qb-url")] = os.environ.get("QB_URL", "")


def load_config():
    config_file = Path(os.getcwd(), "config.toml")

    if not config_file.exists():
        print("please put a config.toml at {}".format(config_file))
        sys.exit(1)

    config: Config = TypeAdapter(Config).validate_python(
        tomli.loads(config_file.read_text())
    )

    return config
