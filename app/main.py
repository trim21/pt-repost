import click
import qbittorrentapi

from app.application import Application
from app.config import get_source_text, load_config
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

    app.db.execute(get_source_text("sql/task.sql"))
    app.db.execute(get_source_text("sql/image.sql"))
    app.db.execute(get_source_text("sql/mediainfo.sql"))

    app.add_task(info_hash.lower(), douban_id=douban)

    app.process_tasks(info_hash.lower())
