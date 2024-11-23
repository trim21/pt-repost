import sqlite3

import click
import qbittorrentapi
from importlib_resources import read_binary
from sslog import logger

from pt_repost.application import Application
from pt_repost.config import load_config
from pt_repost.db import Database


@click.command()
@click.argument("info_hash")
@click.argument("douban")
@click.option("--dry-run", is_flag=True, default=False)
def main(info_hash: str, douban: str, dry_run: bool = False):
    """
    run with

        $ pt-repost info_hash douban_id
    """
    cfg = load_config()

    app = Application(
        db=Database(cfg.db_path),
        config=cfg,
        qb=qbittorrentapi.Client(
            host=str(cfg.qb_url),
            password=cfg.qb_url.password,
            username=cfg.qb_url.username,
            SIMPLE_RESPONSES=True,
            FORCE_SCHEME_FROM_HOST=True,
            VERBOSE_RESPONSE_LOGGING=False,
            RAISE_NOTIMPLEMENTEDERROR_FOR_UNIMPLEMENTED_API_ENDPOINTS=True,
            REQUESTS_ARGS={"timeout": 10},
        ),
    )

    app.db.execute(read_binary("pt_repost", "sql/task.sql").decode())
    app.db.execute(read_binary("pt_repost", "sql/mediainfo.sql").decode())
    app.db.execute(read_binary("pt_repost", "sql/image.sql").decode())

    try:
        app.add_task(info_hash.lower(), douban_id=douban)
    except sqlite3.IntegrityError:
        logger.warning("任务已经存在")

    app.process_tasks(info_hash.lower(), dry_run=dry_run)
