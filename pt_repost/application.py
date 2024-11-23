import dataclasses
import enum
import tempfile
import uuid
from pathlib import Path

import bencode2
import httpx
import qbittorrentapi
import six
import yarl
from qbittorrentapi import TorrentState
from sslog import logger

from pt_repost.config import (
    Config,
    video_ext,
)
from pt_repost.db import Database
from pt_repost.mediainfo import extract_mediainfo_from_file, parse_mediainfo_json
from pt_repost.meta_info import extract_meta_info
from pt_repost.utils import generate_images, human_readable_size, parse_obj_as
from pt_repost.website import SSD


class Status(enum.IntEnum):
    unknown = 0
    downloading = 1
    done = 3


@dataclasses.dataclass(frozen=True, kw_only=True)
class QbFile:
    index: int
    name: str
    size: int
    priority: int
    progress: float


@dataclasses.dataclass(kw_only=True, frozen=True)
class QbTorrent:
    name: str
    hash: str
    state: TorrentState

    save_path: str  # final download path
    completed: int

    total_size: int
    size: int
    amount_left: int


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class Application:
    db: Database
    config: Config
    qb: qbittorrentapi.Client

    def add_task(
        self,
        info_hash,
        site: str = "ssd",
        douban_id: str = "",
        imdb_id: str = "",
    ):
        self.db.execute(
            """
            insert into task (info_hash, site, status, douban_id, imdb_id)
            values (?, ?, ?, ?, ?)
            """,
            [info_hash.lower(), site, Status.unknown, douban_id, imdb_id],
        )

    def process_tasks(self, info_hash: str, dry_run: bool):
        tasks: list[tuple[int, str, str, int, str, str]] = self.db.fetch_all(
            "select task_id,info_hash,site,status,douban_id,imdb_id from task where status != ? and info_hash = ?",
            [Status.done, info_hash],
        )

        for task_id, info_hash, site, status, douban_id, imdb_id in tasks:
            print(task_id, info_hash, site, status)
            torrents = [t for t in self.qb.torrents_info() if t["hash"] == info_hash]
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

            self.process_task(
                task_id,
                info_hash,
                site,
                torrent,
                douban_id,
                imdb_id,
                dry_run=dry_run,
            )

    def process_task(
        self,
        task_id: int,
        info_hash: str,
        site: str,
        t: QbTorrent,
        douban_id: str,
        imdb_id: str,
        dry_run: bool,
    ):
        files = [parse_obj_as(QbFile, x) for x in self.qb.torrents_files(info_hash)]
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

        mediainfo_row = self.db.fetch_one(
            "select mediainfo, mediainfo_json from mediainfo where task_id = ?",
            [task_id],
        )
        if mediainfo_row:
            logger.info("media info already exists, skip generating media info")
            mediainfo_text, mediainfo_json = mediainfo_row
        else:
            logger.info("generating media info")
            mediainfo_text, mediainfo_json = extract_mediainfo_from_file(video_file)
            self.db.execute(
                """
                 insert or ignore into mediainfo (task_id, mediainfo, mediainfo_json)
                 values (?, ?, ?)
                 """,
                [task_id, mediainfo_text, mediainfo_json],
            )

        count = 3

        site_implement = SSD(self.config)

        tc = self.qb.torrents_export(info_hash)

        torrent_name = six.ensure_str(bencode2.bdecode(tc)[b"info"][b"name"])

        options = site_implement.parse_mediainfo_as_options(
            torrent_name, parse_mediainfo_json(mediainfo_json)
        )

        if douban_id:
            url = f"https://movie.douban.com/subject/{douban_id}/"
        elif imdb_id:
            url = f"https://www.imdb.com/title/{imdb_id}/"
        else:
            raise ValueError("missing media site id")

        images = self.db.fetch_all("select * from image where task_id = ?", [task_id])

        if (len(images) < count) and not dry_run:
            with tempfile.TemporaryDirectory(prefix="pt-repost-") as tempdir:
                for file in generate_images(
                    video_file, count=count, tmpdir=Path(tempdir)
                ):
                    url = self.upload_image(file, site)
                    self.db.execute(
                        "insert into image (task_id, url) values (?,?)", [task_id, url]
                    )

        images = [
            x[0]
            for x in self.db.fetch_all(
                "select url from image where task_id = ?", [task_id]
            )
        ]

        info = extract_meta_info(douban_id or imdb_id)
        if dry_run:
            logger.info("dry-run mode, skipping create post")
        else:
            logger.info("create post")
            site_implement.create_post(
                tc,
                mediainfo_text=mediainfo_text,
                images=images,
                options=options,
                url=url,
                info=info,
            )
            self.db.execute(
                "update task set status = ? where task_id = ?", [Status.done, task_id]
            )

    def upload_image(self, file: Path, _site: str):
        return self.upload_pixhost(file)
        # if site == "ssd":
        # return upload_picgo(file)

    # def upload_picgo(file: Path) -> str:
    #     r = picgo_client.post(
    #         "https://www.picgo.net/api/1/upload",
    #         files={"source": (str(uuid.uuid4()) + file.suffix, file.read_bytes())},
    #         data={"format": "json"},
    #         timeout=100,
    #     )
    #
    #     data = r.json()
    #
    #     if data["status_code"] != 200:
    #         raise FailedToUploadImage(data)
    #
    #     return data["image"]["url"]

    def upload_pixhost(self, file: Path) -> str:
        logger.debug(
            "upload image {} size {}", file, human_readable_size(file.lstat().st_size)
        )

        with httpx.Client(proxy=self.config.http_proxy) as http_client:
            r = http_client.post(
                "https://api.pixhost.to/images",
                headers={"accept": "application/json"},
                files={"img": (str(uuid.uuid4()) + file.suffix, file.read_bytes())},
                data={
                    "content_type": "1",
                    "max_th_size": "500",
                },
                timeout=100,
            )

        if r.status_code != 200:
            raise FailedToUploadImage(r.status_code, r.text)

        data = r.json()

        u = yarl.URL(data["show_url"])

        return str(
            u.with_host("img100.pixhost.to").with_path(
                "/images/" + u.path.removeprefix("/show/")
            )
        )


class FailedToUploadImage(Exception):
    pass
