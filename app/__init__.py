import dataclasses
import enum
import tempfile
from pathlib import Path

import click
import qbittorrentapi
from qbittorrentapi import TorrentState
from sslog import logger

from app.config import get_source_text, video_ext, load_config
from app.db import Database
from app.image_host import upload
from app.mediainfo import extract_mediainfo_from_file, parse_mediainfo_json
from app.meta_info import extract_meta_info
from app.utils import generate_images, parse_obj_as
from app.website import SSD


class Status(enum.IntEnum):
    unknown = 0
    downloading = 1
    done = 3


def add_task(
    info_hash,
    db: Database,
    site: str = "ssd",
    douban_id: str = "",
    imdb_id: str = "",
):
    db.execute(
        """
        insert into task (info_hash, site, status, douban_id, imdb_id)
        values (?, ?, ?, ?, ?)
        """,
        [info_hash.lower(), site, Status.unknown, douban_id, imdb_id],
    )


@dataclasses.dataclass(frozen=True, kw_only=True)
class QbFile:
    index: int
    name: str
    size: int
    priority: int
    progress: float


@dataclasses.dataclass(kw_only=True, frozen=True)
class QbTorrent:
    added_on: int
    completion_on: int

    name: str
    hash: str
    state: TorrentState

    progress: float
    save_path: str  # final download path
    content_path: str  # incomplete download path, current file location
    download_path: str | None  # expected incomplete download path
    seen_complete: int
    completed: int
    downloaded: int
    priority: int
    availability: float

    total_size: int
    size: int
    amount_left: int


def process_task(
    task_id: int,
    info_hash: str,
    site: str,
    t: QbTorrent,
    douban_id: str,
    imdb_id: str,
    qb: qbittorrentapi.Client,
    db: Database,
):
    files = [parse_obj_as(QbFile, x) for x in qb.torrents_files(info_hash)]
    files = [f for f in files if f.name.lower().endswith(tuple(video_ext))]
    files.sort(key=lambda x: x.size, reverse=True)
    if not files:
        logger.error("can't find video files for torrent {}", info_hash)
        return

    first_video_file = files[0]
    video_file = Path(t.save_path, first_video_file.name)
    if not video_file.exists():
        logger.error("can't find local file {}".format(video_file))
        return

    mediainfo_row = db.fetch_one(
        "select mediainfo, mediainfo_json from mediainfo where task_id = ?", [task_id]
    )
    if mediainfo_row:
        logger.info("media info already exists, skip generating media info")
        mediainfo_text, mediainfo_json = mediainfo_row
    else:
        logger.info("generating media info")
        mediainfo_text, mediainfo_json = extract_mediainfo_from_file(video_file)
        db.execute(
            """
             insert or ignore into mediainfo (task_id, mediainfo, mediainfo_json)
             values (?, ?, ?)
             """,
            [task_id, mediainfo_text, mediainfo_json],
        )

    count = 3

    images = db.fetch_all("select * from image where task_id = ?", [task_id])

    if len(images) < count:
        with tempfile.TemporaryDirectory(
            dir="/export/ssd-2t/tmp",
            prefix="pt-repost-",
        ) as tempdir:
            for file in generate_images(video_file, count=count, tmpdir=Path(tempdir)):
                url = upload(file, site)
                db.execute(
                    "insert into image (task_id, url) values (?,?)", [task_id, url]
                )

    images = [
        x[0] for x in db.fetch_all("select url from image where task_id = ?", [task_id])
    ]

    site_implement = SSD()

    options = site_implement.parse_mediainfo_as_options(
        str(video_file), parse_mediainfo_json(mediainfo_json)
    )

    if douban_id:
        url = f"https://movie.douban.com/subject/{douban_id}/"
    elif imdb_id:
        url = f"https://www.imdb.com/title/{imdb_id}/"
    else:
        raise ValueError("missing media site id")

    info = extract_meta_info(douban_id or imdb_id)
    logger.info("create post")
    site_implement.create_post(
        qb.torrents_export(info_hash),
        mediainfo_text=mediainfo_text,
        images=images,
        options=options,
        url=url,
        info=info,
    )
    db.execute("update task set status = ? where task_id = ?", [Status.done, task_id])


def process_tasks(info_hash: str, qb: qbittorrentapi.Client, db: Database):
    tasks: list[tuple[int, str, str, int, str, str]] = db.fetch_all(
        "select task_id,info_hash,site,status,douban_id,imdb_id from task where status != ? and info_hash = ?",
        [Status.done, info_hash],
    )

    for task_id, info_hash, site, status, douban_id, imdb_id in tasks:
        print(task_id, info_hash, site, status)
        torrents = [t for t in qb.torrents_info() if t["hash"] == info_hash]
        if not torrents:
            logger.warning("{} is not downloading", info_hash)
            continue
        assert len(torrents) == 1
        torrent = parse_obj_as(QbTorrent, torrents[0])
        if not (
            torrent.state.is_uploading
            and torrent.state.is_complete
            and (torrent.state != torrent.state.MOVING)
        ):
            logger.trace("{} is still download/moving", info_hash)
            continue

        if torrent.total_size != torrent.completed:
            logger.trace("{} is partial downloaded", info_hash)
            continue

        process_task(task_id, info_hash, site, torrent, douban_id, imdb_id, qb)


@click.command()
@click.argument("info_hash")
@click.argument("douban")
def main(info_hash: str, douban: str):
    config = load_config()
    db = Database(config.db_path)

    db.execute(get_source_text("sql/task.sql"))
    db.execute(get_source_text("sql/image.sql"))
    db.execute(get_source_text("sql/mediainfo.sql"))

    add_task(info_hash.lower(), douban_id=douban)

    qb = qbittorrentapi.Client(
        host=config.qb_url,
        SIMPLE_RESPONSES=True,
        FORCE_SCHEME_FROM_HOST=True,
        VERBOSE_RESPONSE_LOGGING=False,
        RAISE_NOTIMPLEMENTEDERROR_FOR_UNIMPLEMENTED_API_ENDPOINTS=True,
        REQUESTS_ARGS={"timeout": 10},
    )

    process_tasks(info_hash.lower(), qb)
