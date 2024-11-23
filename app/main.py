import sqlite3

import click
import qbittorrentapi
from importlib_resources import read_text
from sslog import logger

from app.application import Application
from app.config import load_config
from app.db import Database


@click.command()
@click.argument("info_hash")
@click.argument("douban")
def main(info_hash: str, douban: str):
    """
    run with

        $ pt-repost info_hash douban_id
    """
    cfg = load_config()

    app = Application(
        db=Database(cfg.db_path),
        config=cfg,
        qb=qbittorrentapi.Client(
            host=cfg.qb_url,
            SIMPLE_RESPONSES=True,
            FORCE_SCHEME_FROM_HOST=True,
            VERBOSE_RESPONSE_LOGGING=False,
            RAISE_NOTIMPLEMENTEDERROR_FOR_UNIMPLEMENTED_API_ENDPOINTS=True,
            REQUESTS_ARGS={"timeout": 10},
        ),
    )

    app.db.execute(read_text("app", "sql/task.sql"))
    app.db.execute(read_text("app", "sql/mediainfo.sql"))
    app.db.execute(read_text("app", "sql/image.sql"))

    try:
        app.add_task(info_hash.lower(), douban_id=douban)
    except sqlite3.IntegrityError:
        logger.warning("任务已经存在")

    app.process_tasks(info_hash.lower())
