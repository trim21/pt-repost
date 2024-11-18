import dataclasses
import os
from pathlib import Path

import tomli
from pydantic import TypeAdapter

QB_URL = os.environ.get("QB_URL") or "https://qb.omv.trim21.me"

PROJECT_PATH = Path(__file__, "../..").resolve()

video_ext = {".mkv", ".mp4", ".ts"}


@dataclasses.dataclass(frozen=True, slots=True)
class SSD:
    cookies: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class Website:
    ssd: SSD


@dataclasses.dataclass(frozen=True, slots=True)
class Config:
    website: Website
    http_proxy: str | None = None
    db_path: Path = Path(
        os.environ.get("SQLITE_DB_FILE") or PROJECT_PATH.joinpath("data.db")
    )


config: Config = TypeAdapter(Config).validate_python(
    tomli.loads(Path("config.toml").read_text())
)


SQLITE_DB_FILE = config.db_path
