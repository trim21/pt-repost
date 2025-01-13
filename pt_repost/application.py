from __future__ import annotations

import dataclasses
import enum
import functools
import io
import json
import re
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime as _parsedate_to_datetime
from pathlib import Path
from typing import Annotated, Any, TypeVar, cast
from xml.etree import ElementTree

import annotated_types
import bencode2
import guessit
import httpx
import orjson
import qbittorrentapi
import xxhash
import yarl
from pydantic import Field
from qbittorrentapi import TorrentState
from rich.console import Console
from rich.table import Table
from sslog import logger
from uuid_utils import uuid7

from pt_repost.config import Config, video_ext
from pt_repost.const import (
    DEFAULT_HEADERS,
    LOCK_KEY_SCHEDULE_RSS,
    QB_CATEGORY,
    RSS_ITEM_STATUS_DONE,
    RSS_ITEM_STATUS_DOWNLOADING,
    RSS_ITEM_STATUS_FAILED,
    RSS_ITEM_STATUS_PENDING,
    RSS_ITEM_STATUS_PROCESSING,
    RSS_ITEM_STATUS_REMOVED_FROM_DOWNLOAD_CLIENT,
    RSS_ITEM_STATUS_REMOVED_FROM_SITE,
    RSS_ITEM_STATUS_SKIPPED,
    RSS_ITEM_STATUS_UPLOADING,
    SSD_REMOVED_MESSAGE,
    TASK_STATUS_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCESS,
)
from pt_repost.db import Database
from pt_repost.douban import DoubanSubject
from pt_repost.hardcode_subtitle import check_hardcode_chinese_subtitle
from pt_repost.mediainfo import extract_mediainfo_from_file, parse_mediainfo_json
from pt_repost.patterns import pattern_web_dl
from pt_repost.tmdb import (
    FullSubjectInfo,
    TMDBMovieDetail,
    TMDBMovieInfo,
    TMDBMovieSearchResult,
    TMDBTvDetail,
    TMDBTvSearchResult,
)
from pt_repost.utils import (
    an2cn,
    generate_images,
    get_info_hash_v1_from_content,
    human_readable_size,
    parse_json_as,
    parse_obj_as,
)
from pt_repost.website import SSD


def format_exc(e: Exception) -> str:
    f = io.StringIO()
    with f:
        f.write(f"{type(e)}: {e}\n")
        Console(legacy_windows=True, width=1000, file=f, no_color=True).print_exception()
        return f.getvalue()


class Skip(Exception):
    def __init__(self, guid: str, website: str, reason: str = ""):
        super().__init__()
        self.guid: str = guid
        self.website: str = website
        self.reason: str = reason


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

    uploaded: int

    total_size: int
    size: int
    amount_left: int

    num_seeds: int


@dataclasses.dataclass(kw_only=True, frozen=True)
class QbTracker:
    msg: str
    tier: int


console = Console(emoji=False, force_terminal=True, no_color=False, legacy_windows=True)


@dataclasses.dataclass
class Processing:
    release_title: str


@dataclasses.dataclass(kw_only=True, frozen=True)
class Application:
    db: Database
    config: Config
    qb: qbittorrentapi.Client

    tmdb_client: httpx.Client

    douban_client: httpx.Client = dataclasses.field(default_factory=httpx.Client)

    @classmethod
    def new(cls, cfg: Config) -> Application:
        tmdb_client = httpx.Client(
            proxy=cfg.http_proxy or None,
            headers={
                "accept": "application/json",
                "Authorization": f"Bearer {cfg.tmdb_api_token}",
            },
        )

        return Application(
            config=cfg,
            db=Database(cfg),
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
            tmdb_client=tmdb_client,
        )

    def __post_init__(self) -> None:
        try:
            self.db.fetch_val("select version()")
        except Exception as e:
            print("failed to connect to database", e)
            raise

        print("successfully connect to database")

        for sql_file in Path(__file__, "../sql/").resolve().iterdir():
            print("executing {}".format(sql_file.name))
            self.db.execute(sql_file.read_text(encoding="utf-8"))

        try:
            self.qb.app_version()
        except Exception as e:
            print("failed to connect to qBittorrent", e)
            raise
        print("successfully connect to qBittorrent")

    def start(self) -> None:
        for rss_id, rss in enumerate(self.config.rss):
            self.db.execute(
                """
            insert into rss (id, url, exclude_url, website, includes, excludes, interval_seconds)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            on conflict (id) do update set
                url = excluded.url,
                exclude_url = excluded.exclude_url,
                website = excluded.website,
                includes = excluded.includes,
                excludes = excluded.excludes,
                interval_seconds = excluded.interval_seconds
            """,
                [
                    rss_id,
                    rss.url,
                    rss.exclude_url,
                    rss.website,
                    json.dumps(rss.includes),
                    json.dumps(rss.excludes),
                    rss.interval,
                ],
            )

        interval = 1
        while True:
            self.__heart_beat()
            time.sleep(interval)
            interval = 60
            try:
                self.__run_at_interval()
            except Exception as e:
                print("failed to run", e)

    def __run_at_interval(self) -> None:
        self.__process_local_uploading()
        self.__process_local_downloading()
        self.__fetch_rss()
        self.__pick_rss_item()
        self.__debug_report()

    def __debug_report(self) -> None:
        if not self.config.debug:
            return
        rows = cast(
            list[tuple[str, str, datetime, float]],
            self.db.fetch_all(
                """
                select title,status,updated_at,progress
                 from rss_item where status = any($1)
                 order by updated_at
                """,
                [list(RSS_ITEM_STATUS_PROCESSING)],
            ),
        )

        if not rows:
            return

        table = Table()

        table.add_column("Updated At")
        table.add_column("Status")
        table.add_column("Progress")
        table.add_column("Title")

        for title, status, updated_at, progress in rows:
            if status != RSS_ITEM_STATUS_DOWNLOADING:
                progress_str = ""
            else:
                progress_str = "{:05.2f} %".format(progress * 100)

            table.add_row(
                str(updated_at.replace(microsecond=0).astimezone()),
                status,
                progress_str,
                title,
            )

        console.print(table)

    def process_task(self, t: QbTorrent) -> None:
        files = [parse_obj_as(QbFile, x) for x in self.qb.torrents_files(t.hash)]
        files = [f for f in files if f.name.lower().endswith(video_ext)]
        files.sort(key=lambda x: x.size, reverse=True)
        if not files:
            logger.error("can't find video files for torrent {}", t.hash)
            return

        first_video_file = files[0]
        video_file = Path(t.save_path, first_video_file.name)
        if not video_file.exists():
            logger.error("can't find local file {}".format(video_file))
            return

        mediainfo_row = self.db.fetch_one(
            "select mediainfo_text, mediainfo_json from mediainfo where info_hash = $1",
            [t.hash],
        )
        if mediainfo_row:
            mediainfo_text, mediainfo_json = mediainfo_row
        else:
            logger.info("generating media info")
            mediainfo_text, mediainfo_json = extract_mediainfo_from_file(video_file)
            self.db.execute(
                """
                 insert into mediainfo (info_hash, mediainfo_text, mediainfo_json)
                 values ($1, $2, $3)
                 on conflict (info_hash) do nothing
                 """,
                [t.hash, mediainfo_text, mediainfo_json],
            )

        count = 4

        # should save db in early and get description from db
        title, meta_info, hard_code_chinese_subtitle, douban_id, imdb_id = cast(
            tuple[str, Any, bool, str, str],
            self.db.fetch_one(
                "select title, meta_info,hard_code_chinese_subtitle,douban_id,imdb_id from rss_item where info_hash = $1 limit 1",
                [t.hash],
            ),
        )

        images = [
            t[0] for t in self.db.fetch_all("select url from image where info_hash = $1", [t.hash])
        ]

        if len(images) < count:
            images = []
            self.db.execute("delete from image where info_hash = $1", [t.hash])
            with tempfile.TemporaryDirectory(prefix="pt-repost-") as tempdir:
                image_format = "png"
                if pattern_web_dl.search(title):
                    image_format = "jpg"

                image_files = list(
                    generate_images(
                        video_file,
                        count=count,
                        tmpdir=Path(tempdir),
                        image_format=image_format,
                    )
                )

                hard_code_chinese_subtitle = check_hardcode_chinese_subtitle(image_files)
                if hard_code_chinese_subtitle:
                    self.db.execute(
                        """update rss_item set hard_code_chinese_subtitle = true where info_hash = $1""",
                        [t.hash],
                    )

                for file in image_files:
                    retry_count = 0

                    while True:
                        try:
                            url = self.upload_image(file, self.config.target_website)
                            break
                        except Exception as e:
                            retry_count += 1
                            logger.warning(
                                "failed to upload image, retry count {}: {}",
                                retry_count,
                                e,
                            )

                            if retry_count >= 5:
                                raise

                    logger.info("uploaded image url {!r}", url)
                    self.db.execute(
                        "insert into image (info_hash, url, uuid) values ($1, $2, $3)",
                        [t.hash, url, str(uuid7())],
                    )
                    images.append(url)

        site_implement = SSD(self.config)

        options = site_implement.parse_mediainfo_as_options(
            title, parse_mediainfo_json(mediainfo_json)
        )

        if isinstance(site_implement, SSD):
            if hard_code_chinese_subtitle:
                options["subtitlezh"] = "1"

        tc = self.export_torrent(t.hash)

        logger.info("create post")

        info = parse_json_as(FullSubjectInfo, meta_info)

        # clean old torrent tracker info
        torrent_data = bencode2.bdecode(tc)
        torrent_data[b"info"][b"private"] = 1
        torrent_data.pop(b"announce", None)
        torrent_data.pop(b"announce-list", None)
        tc = bencode2.bencode(torrent_data)

        if douban_id:
            info = dataclasses.replace(info, douban_id=douban_id)
        if imdb_id:
            info = dataclasses.replace(info, imdb_id=imdb_id)

        new_torrent = site_implement.create_post(
            tc,
            release_name=fix_title(title, tc, info),
            mediainfo_text=mediainfo_text,
            images=images,
            options=options,
            info=info,
        )

        self.qb.torrents_add(
            torrent_files=new_torrent,
            save_path=t.save_path,
            is_skip_checking=True,
            category=QB_CATEGORY,
            tags="pt-repost",
            use_auto_torrent_management=False,
        )

        new_info_hash = get_info_hash_v1_from_content(new_torrent)

        self.db.execute(
            """
            update rss_item set
                status = $1,
                target_info_hash = $2,
                updated_at = current_timestamp,
                progress = 0
            where info_hash = $3
            """,
            [RSS_ITEM_STATUS_UPLOADING, new_info_hash, t.hash],
        )

    def __process_local_downloading(self) -> None:
        """
        may move torrent from download status to uploading status
        """
        self.db.execute(
            """
            update rss_item
             set status = $1
             where status = $2 and info_hash = $3 and picked_node = $4
            """,
            [
                RSS_ITEM_STATUS_PENDING,
                RSS_ITEM_STATUS_DOWNLOADING,
                "",
                self.config.node_id,
            ],
        )
        downloading = {
            row[0]
            for row in self.db.fetch_all(
                """select info_hash from rss_item where status = $1""",
                [RSS_ITEM_STATUS_DOWNLOADING],
            )
        }

        local_torrents = parse_obj_as(list[QbTorrent], self.qb.torrents_info(category=QB_CATEGORY))
        local_hashes = {t.hash for t in local_torrents}

        missing_in_local_downloads = {h for h in downloading if h not in local_hashes}
        if missing_in_local_downloads:
            self.db.execute(
                """
                update rss_item
                 set status = $1, updated_at = current_timestamp
                where info_hash = any($2)
                """,
                [
                    RSS_ITEM_STATUS_REMOVED_FROM_DOWNLOAD_CLIENT,
                    list(missing_in_local_downloads),
                ],
            )

        for t in local_torrents:
            if t.hash not in downloading:
                continue
            if not t.state.is_uploading:
                # with contextlib.suppress(Exception):
                try:
                    self.db.execute(
                        "update rss_item set progress = $1 where info_hash = $2",
                        [t.completed / t.total_size, t.hash],
                    )
                except Exception as e:
                    logger.warning("failed to update torrent progress {}", e)
                continue

            try:
                self.process_task(t=t)
            except Exception as e:
                logger.warning("failed to process task {!r} {}", e, e)
                self.db.execute(
                    """
                    update rss_item set status = $1,
                     failed_reason = $2,
                     updated_at = current_timestamp
                    where info_hash = $3
                    """,
                    [
                        RSS_ITEM_STATUS_FAILED,  # 1
                        format_exc(e),  # 2
                        t.hash,
                    ],
                )

    def __process_local_uploading(self) -> None:
        uploading = {
            x[0]
            for x in self.db.fetch_all(
                "select target_info_hash from rss_item where picked_node = $1 and status = $2",
                [self.config.node_id, RSS_ITEM_STATUS_UPLOADING],
            )
        }

        local_hashes = {t["hash"] for t in self.qb.torrents_info(category=QB_CATEGORY)}

        local_removed = {t for t in uploading if t not in local_hashes}

        if local_removed:
            self.db.execute(
                """
                update rss_item set status = $1, updated_at = current_timestamp
                 where target_info_hash = any($2)
                """,
                [RSS_ITEM_STATUS_REMOVED_FROM_DOWNLOAD_CLIENT, list(local_removed)],
            )

        removed_torrents = set()

        for t in parse_obj_as(list[QbTorrent], self.qb.torrents_info(status_filter="seeding")):
            if t.hash not in uploading:
                continue
            for tracker in parse_obj_as(list[QbTracker], self.qb.torrents_trackers(t.hash)):
                if tracker.tier < 0:
                    continue
                if tracker.msg == SSD_REMOVED_MESSAGE:
                    logger.info("removed by website: {!r}", t.name)
                    removed_torrents.add(t.hash)
                    break

        if removed_torrents:
            self.db.execute(
                """
                    update rss_item set status = $1, updated_at = current_timestamp
                    where target_info_hash = any($2)""",
                [RSS_ITEM_STATUS_REMOVED_FROM_SITE, list(removed_torrents)],
            )

        uploading = uploading - removed_torrents

        done_torrents = set()

        for t in parse_obj_as(list[QbTorrent], self.qb.torrents_info(status_filter="seeding")):
            if t.hash not in uploading:
                continue
            if t.uploaded <= t.total_size:
                continue
            if t.completed <= 4:
                continue
            done_torrents.add(t.hash)

        # TODO: delete torrent contents

        if done_torrents:
            self.db.execute(
                """
                update rss_item set status = $1, updated_at = current_timestamp
                 where target_info_hash = any($2)
                """,
                [RSS_ITEM_STATUS_DONE, list(done_torrents)],
            )

    def get_meta_info(self, pick: Pick) -> FullSubjectInfo:
        guess: dict[str, Any] = guessit.guessit(pick.title)

        match guess.get("type"):
            case "episode":
                return self.__get_meta_info_for_episodes(pick.title, guess)
            case "movie":
                return self.__get_meta_info_for_movie(pick.title, guess)
            case v:
                raise NotImplementedError("unexpected release type {}".format(v))

    def __get_meta_info_for_episodes(
        self,
        release_title: str,
        guess: dict[str, Any],
    ) -> FullSubjectInfo:
        q = {"query": guess["title"]}
        if "year" in guess:
            q["year"] = guess["year"]

        res = self.tmdb_client.get("https://api.themoviedb.org/3/search/tv", params=q)

        search_result = parse_obj_as(TMDBTvSearchResult, res.json())

        results = search_result.results

        if not results:
            raise Exception(
                "failed to parse tmdb info, can't find any results for {!r}, q: {!r}".format(
                    guess["title"], q
                )
            )

        if len(results) != 1:
            try_guess = [t for t in results if t.name == guess["title"]]
            # not perfect match
            if len(try_guess) != 1:
                raise Exception(
                    "failed to parse tmdb info, multiple match for search words for query {} {!r}\n{}".format(
                        q, guess["title"], [t.name for t in results]
                    )
                )
            results = try_guess

        basic_info = results[0]

        info = parse_obj_as(
            TMDBTvDetail,
            self.tmdb_client.get(
                f"https://api.themoviedb.org/3/tv/{basic_info.id}",
                params={"language": "zh-CN", "append_to_response": "external_ids"},
            ).json(),
        )

        if not info.external_ids.imdb_id:
            raise Exception("failed to find imdb id for {!r}".format(release_title))

        douban_id = None

        names = [info.name, info.original_name]

        douban_info = self._get_douban_id_from_imdb(info.external_ids.imdb_id, guess["season"])

        if douban_info:
            douban_id = douban_info.id.rsplit("/")[-1]
            # 豆瓣的 `title` 是原文标题
            if douban_info.alt_title:
                names.extend(t.strip() for t in douban_info.alt_title.split("/"))

        episode_count = [s for s in info.seasons if s.season_number == guess["season"]][
            0
        ].episode_count

        return FullSubjectInfo(
            id=info.id,
            names=names,
            episode_count=episode_count,
            genre_ids=basic_info.genre_ids,
            origin_country=info.origin_country,
            imdb_id=info.external_ids.imdb_id,
            douban_id=douban_id,
            release_type="tv",
        )

    def __get_meta_info_for_movie(
        self,
        release_title: str,
        guess: dict[str, Any],
    ) -> FullSubjectInfo:
        q = {"query": guess["title"]}
        if "year" in guess:
            q["year"] = guess["year"]

        res = self.tmdb_client.get("https://api.themoviedb.org/3/search/movie", params=q)

        search_result = parse_obj_as(TMDBMovieSearchResult, res.json())

        results: list[TMDBMovieInfo] = search_result.results

        if not results:
            raise Exception(
                "failed to parse tmdb info, can't find any results for {!r}, q: {!r}".format(
                    guess["title"], q
                )
            )

        # not perfect match
        if len(results) != 1:
            try_guess = [t for t in results if t.title == guess["title"]]
            if len(try_guess) != 1:
                raise Exception(
                    "failed to parse tmdb info, multiple match for search words for query {} {!r}\n{}".format(
                        q, guess["title"], [t.title for t in results]
                    )
                )
            results = try_guess

        basic_info: TMDBMovieInfo = results[0]

        info = parse_obj_as(
            TMDBMovieDetail,
            self.tmdb_client.get(
                f"https://api.themoviedb.org/3/movie/{basic_info.id}",
                params={"language": "zh-CN"},
            ).json(),
        )

        if not info.imdb_id:
            raise Exception("failed to find imdb id for {!r}".format(release_title))

        douban_id = None

        names = [info.title, info.original_title]

        douban_info = self._get_douban_id_from_imdb(info.imdb_id)

        if douban_info:
            douban_id = douban_info.id.rsplit("/")[-1]
            # 豆瓣的 `title` 是原文标题
            if douban_info.alt_title:
                names.extend(t.strip() for t in douban_info.alt_title.split("/"))

        return FullSubjectInfo(
            id=info.id,
            names=names,
            genre_ids=basic_info.genre_ids,
            origin_country=info.origin_country,
            imdb_id=info.imdb_id,
            douban_id=douban_id,
            release_type="movie",
        )

    def _get_douban_id_from_imdb(self, imdb_id: str, season: int = 1) -> DoubanSubject | None:
        row: tuple[int, str, Any] | None = self.db.fetch_one(
            "select season, douban_id, douban_info from imdb where id = $1 and season = $2 limit 1",
            [imdb_id, season],
        )
        if row:
            return parse_obj_as(DoubanSubject, orjson.loads(row[2]))

        res = self.douban_client.post(
            f"http://api.douban.com/v2/movie/imdb/{imdb_id}",
            data={"apikey": "0ab215a8b1977939201640fa14c66bab"},
        )
        if res.status_code == 404:
            return None

        data = res.json()

        douban_id = data["id"]

        if season != 1:
            alt_title: str = data["alt_title"]
            if alt_title:
                title = alt_title.split("/")[0]
                title.strip()
            else:
                title = data["title"]

            res = self.douban_client.post(
                "http://api.douban.com/v2/movie/search",
                data={"apikey": "0ab215a8b1977939201640fa14c66bab"},
                params={"q": title + f" 第{an2cn(season)}季"},
            )

            search_result = res.json()["subjects"]
            if search_result:
                data = search_result[0]
                douban_id = data["id"].rsplit("/")[-1]

        self.db.execute(
            """
            insert into imdb (id, season, douban_id, douban_info)
             VALUES ($1, $2, $3, $4)
              on conflict (id, season) do update set
               douban_id = excluded.douban_id,
               douban_info = excluded.douban_info
            """,
            [imdb_id, season, douban_id, orjson.dumps(data).decode()],
        )

        return parse_obj_as(DoubanSubject, data)

    def __heart_beat(self) -> None:
        self.db.execute(
            """
            insert into node (id, last_seen) values ($1, $2)
            on conflict (id) do update set last_seen = excluded.last_seen
            """,
            [self.config.node_id, datetime.now(tz=timezone.utc)],
        )

    def export_torrent(self, info_hash: str) -> bytes:
        return self.qb.torrents_export(info_hash)

    def upload_image(self, file: Path, _site: str) -> str:
        return self.upload_cmct(file)

    def upload_cmct(self, file: Path) -> str:
        image_content = file.read_bytes()

        r = httpx.post(
            "https://cmct.xyz/api/1/upload",
            headers={
                "X-API-Key": self.config.images.cmct_api_token,
            },
            files={"source": (file.name, image_content)},
            data={"format": "json"},
        )

        if r.status_code != 200:
            raise FailedToUploadImage(r.status_code, r.text)

        data = r.json()

        if data["status_code"] != 200:
            raise FailedToUploadImage(r.status_code, r.text)

        return data["image"]["url"]

    def upload_pixhost(self, file: Path) -> str:
        """被pixhost拉黑了，暂时无法使用"""

        image_content = file.read_bytes()
        logger.debug(
            "upload image {} size {}",
            file,
            human_readable_size(len(image_content)),
        )

        with httpx.Client(proxy=self.config.http_proxy) as http_client:
            r = http_client.post(
                "https://api.pixhost.to/images",
                headers={"accept": "application/json"},
                files={"img": (str(uuid.uuid4()) + file.suffix, image_content)},
                data={"content_type": "1", "max_th_size": "500"},
                timeout=120,
            )

            if r.status_code != 200:
                raise FailedToUploadImage(r.status_code, r.text)

            data = r.json()

        u = yarl.URL(data["show_url"])

        return str(
            u.with_host("img100.pixhost.to").with_path("/images/" + u.path.removeprefix("/show/"))
        )

    def __fetch_rss(self) -> None:
        logger.info("schedule for fetch rss job")
        process_rss_task = None
        run_id = None
        with (
            self.db.lock(LOCK_KEY_SCHEDULE_RSS),
            self.db.connection() as conn,
            conn.transaction(),
        ):
            conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            for rss_id, url, exclude_url, website, includes, excludes, interval in cast(
                list[tuple[int, str, str, str, list[str | list[str]], list[str], int]],
                conn.execute(
                    "select id,url,exclude_url,website,includes,excludes,interval_seconds from rss order by id"
                ).fetchall(),
            ):
                if not conn.fetch_val(
                    "select count(1) from rss_run where rss_id = $1 and created_at > $2",
                    [
                        rss_id,
                        datetime.now().astimezone() - timedelta(seconds=interval),
                    ],
                ):
                    run_id = conn.fetch_val(
                        """
                        insert into rss_run (rss_id, node_id, created_at, status)
                         values ($1, $2, $3, $4)
                        returning id
                        """,
                        [
                            rss_id,
                            self.config.node_id,
                            datetime.now().astimezone(),
                            TASK_STATUS_RUNNING,
                        ],
                    )
                    process_rss_task = (
                        rss_id,
                        url,
                        exclude_url,
                        website,
                        includes,
                        excludes,
                    )
                    break

        if process_rss_task is not None:
            rss_id, url, exclude_url, website, includes, excludes = process_rss_task
            try:
                logger.info("fetch rss {} {}", website, rss_id)
                self.process_rss_run(url, exclude_url, website, includes, excludes)
                logger.info("fetch successfully {} {}", website, rss_id)
                self.db.execute(
                    """
                    update rss_run set status = $1 where id=$2
                    """,
                    [TASK_STATUS_SUCCESS, run_id],
                )
            except Exception as e:
                console.print_exception()
                print("failed to fetch rss {}", e)
                self.db.execute(
                    """
                    update rss_run set status = $1, failed_reason = $2 where id=$3
                    """,
                    [TASK_STATUS_FAILED, format_exc(e), run_id],
                )

    def __pick_rss_item(self) -> None:
        while True:
            picked = self.pick_rss_item()
            if not picked:
                logger.info("pick 0 new rss items")
                break
            self.process_new_picked(picked)

    def process_new_picked(self, picked: list[Pick]) -> None:
        logger.info("pick {} new rss item", len(picked))
        for pick in picked:
            try:
                self.__process_new_pick(pick)
            except Skip as e:
                logger.info("skip torrent {} {} {}", pick.website, pick.guid, e.reason)
                self.db.execute(
                    """
                    update rss_item set status = $1,
                        updated_at = current_timestamp
                    where guid = $2 and website = $3
                    """,
                    [RSS_ITEM_STATUS_SKIPPED, pick.guid, pick.website],
                )

            except Exception as e:
                console.print_exception()
                logger.error("failed to handle {!r}: {}", pick.title, e)
                self.db.execute(
                    """
                    update rss_item set status = $1,
                        failed_reason = $2,
                        updated_at = current_timestamp
                    where guid = $3 and website = $4
                    """,
                    [
                        RSS_ITEM_STATUS_FAILED,  # 1
                        format_exc(e),  # 2
                        pick.guid,  # 3
                        pick.website,  # 4
                    ],
                )

    def __process_new_pick(self, pick: Pick) -> None:
        meta_info = self.get_meta_info(pick)

        self.db.execute(
            "update rss_item set meta_info=$1 where guid=$2 and website=$3",
            [
                orjson.dumps(meta_info).decode(),  # 1
                pick.guid,  # 2
                pick.website,  # 3
            ],
        )

        if 16 in meta_info.genre_ids:
            raise Skip(pick.guid, pick.website, "动画")

        tc = httpx.get(
            pick.link,
            proxy=self.config.http_proxy,
            headers=DEFAULT_HEADERS,
            timeout=30,
            follow_redirects=True,
        )
        if tc.is_error:
            raise Exception("failed to download torrent {}".format(tc.text))

        try:
            info_hash = get_info_hash_v1_from_content(tc.content)
        except bencode2.BencodeDecodeError:
            print(pick.link)
            print(tc.text)
            raise

        self.db.execute(
            "update rss_item set info_hash = $1 where guid = $2 and website = $3",
            [info_hash, pick.guid, pick.website],
        )

        self.qb.torrents_add(
            torrent_files=tc.content,
            category="pt-repost",
            tags="pt-repost",
            add_to_top_of_queue=False,
        )

    def pick_rss_item(self) -> list[Pick]:
        logger.info("schedule for pick rss item")
        picked: list[Pick] = []

        # maybe use a SERIALIZABLE isolation_level instead
        with self.db.connection() as conn, conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            current_processing = conn.execute(
                """
                    select size,status,info_hash from rss_item
                    where picked_node = $1 and status = any($2)
                    """,
                [
                    self.config.node_id,
                    list(RSS_ITEM_STATUS_PROCESSING),
                ],
            ).fetchall()

            current_total_size = sum(t[0] for t in current_processing)
            rest = self.config.max_processing_size - current_total_size

            if len(current_processing) >= self.config.max_processing_per_node:
                return []

            released_after = datetime.fromtimestamp(
                time.time() - self.config.recent_release_seconds, tz=timezone.utc
            ).astimezone()

            logger.info("pick release data after {}", released_after.replace(microsecond=0))

            rss_items: list[tuple[str, str, str, datetime, int, str, str, str]] = conn.fetch_all(
                """
                    select guid,website,link,released_at,size,title,imdb_id,douban_id
                    from rss_item where status = $1 and size <= $2 and released_at >= $3
                    order by released_at desc
                    """,
                [
                    RSS_ITEM_STATUS_PENDING,
                    rest,
                    released_after,
                ],
            )

            for (
                guid,
                website,
                link,
                released_at,
                size,
                title,
                imdb_id,
                douban_id,
            ) in rss_items:
                if len(picked) + len(current_processing) >= self.config.max_processing_per_node:
                    break

                if rest - size <= 0:
                    continue

                if size >= self.config.max_single_torrent_size:
                    continue

                if self.config.excludes:
                    if any(p.search(title) for p in self.config.excludes):
                        continue

                if self.config.includes:
                    if all(p.search(title) for p in self.config.includes):
                        continue

                rest -= size
                picked.append(
                    Pick(
                        guid=guid,
                        website=website,
                        link=link,
                        released_at=released_at,
                        size=size,
                        title=title,
                        imdb_id=imdb_id,
                        douban_id=douban_id,
                    )
                )
                conn.execute(
                    """
                        update rss_item
                        set status = $1,
                            picked_node = $2,
                            updated_at = current_timestamp
                        where guid = $3 and website = $4
                        """,
                    [RSS_ITEM_STATUS_DOWNLOADING, self.config.node_id, guid, website],
                )

        return picked

    def process_rss_run(
        self,
        url: str,
        exclude_url: str,
        website: str,
        includes: list[str | list[str]],
        excludes: list[str],
    ) -> None:
        if exclude_url:
            self.__process_exclude_rss(
                httpx.get(exclude_url, proxy=self.config.http_proxy, timeout=30).text,
                website,
            )

        if self.config.debug:
            debug_rss_url = self.config.data_dir.joinpath(xxhash.xxh3_64_hexdigest(url) + ".rss")
            if debug_rss_url.exists():
                rss_text = debug_rss_url.read_text(encoding="utf-8")
            else:
                res = httpx.get(url, proxy=self.config.http_proxy, timeout=30)
                rss_text = res.text
            if self.config.debug:
                debug_rss_url.write_text(rss_text, encoding="utf-8")
        else:
            res = httpx.get(url, timeout=30, proxy=self.config.http_proxy)
            rss_text = res.text

        self.process_rss(
            rss_text,
            website,
            includes=[self.compile_patterns(s) for s in includes],
            excludes=[self._compile_pattern(s) for s in excludes],
        )

    @classmethod
    def compile_patterns(cls, s: str | list[str]) -> re.Pattern[str] | list[re.Pattern[str]]:
        if isinstance(s, list):
            return [cls._compile_pattern(p) for p in s]

        return cls._compile_pattern(s)

    @staticmethod
    @functools.lru_cache(maxsize=1024)
    def _compile_pattern(s: str) -> re.Pattern[str]:
        return re.compile(s)

    def __process_exclude_rss(
        self,
        rss_text: str,
        website: str,
    ) -> None:
        try:
            et: ElementTree.Element = ElementTree.fromstring(rss_text)
        except ElementTree.ParseError:
            raise

        for item_el in et.findall("channel/item"):
            item = parse_rss_item(item_el)
            self.db.execute(
                """
            insert into rss_item (guid, website, link, title, released_at, status, size, imdb_id, douban_id)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
             on conflict (guid, website) do update set status = excluded.status
            """,
                [
                    item.guid,  # 1
                    website,  # 2
                    item.link,  # 3
                    item.title,  # 4
                    item.pub_date or datetime.now().astimezone(),  # 5
                    RSS_ITEM_STATUS_SKIPPED,  # 6
                    item.size,  # 7
                    item.imdb_id or "",  # 8
                    item.douban_id or "",  # 9
                ],
            )

    def __match_includes(
        self,
        title: str,
        patterns: list[re.Pattern[str] | list[re.Pattern[str]]],
    ) -> bool:
        if not patterns:
            return True

        for pattern in patterns:
            if isinstance(pattern, list):
                if all(p.search(title) for p in pattern):
                    return True
            else:
                if pattern.search(title):
                    return True

        return False

    def process_rss(
        self,
        rss_text: str,
        website: str,
        includes: list[re.Pattern[str] | list[re.Pattern[str]]],
        excludes: list[re.Pattern[str]],
    ) -> None:
        try:
            et: ElementTree.Element = ElementTree.fromstring(rss_text)
        except ElementTree.ParseError:
            raise

        items = []

        for item_el in et.findall("channel/item"):
            item = parse_rss_item(item_el)

            if excludes:
                if any(p.search(item.title) for p in excludes):
                    continue

            if not self.__match_includes(item.title, includes):
                continue

            if self.config.excludes:
                if any(p.search(item.title) for p in self.config.excludes):
                    continue

            if self.config.includes:
                if all(p.search(item.title) for p in self.config.includes):
                    continue

            items.append(item)

        logger.info("{} items", len(items))

        for item in items:
            self.db.execute(
                """
            insert into rss_item (guid, website, link, title, released_at, status, size, imdb_id, douban_id)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
             on conflict (guid, website) do nothing
            """,
                [
                    item.guid,  # 1
                    website,  # 2
                    item.link,  # 3
                    item.title,  # 4
                    item.pub_date or datetime.now().astimezone(),  # 5
                    RSS_ITEM_STATUS_PENDING,  # 6
                    item.size,  # 7
                    item.imdb_id or "",  # 8
                    item.douban_id or "",  # 9
                ],
            )


pattern_episodes = re.compile(r"\bS\d+E(?P<episode>\d+)\b", re.IGNORECASE)
pattern_season_only = re.compile(r"(\b)(S\d+)(\b)", re.IGNORECASE)


def fix_title(title: str, torrent: bytes, meta_info: FullSubjectInfo) -> str:
    if meta_info.release_type != "tv":
        return title

    if pattern_episodes.match(title):
        # title with episode, no need to fix
        # for example
        # Riverside.Code.at.Qingming.Festival.S01E06-E07.2024.2160p.WEB-DL.H265.AAC-Group
        return title

    if not meta_info.episode_count:
        return title

    torrent_info: dict[str, Any] = _transform_info(bencode2.bdecode(torrent)[b"info"])
    if not torrent_info.get("files"):
        return title

    torrent_files = parse_obj_as(list[File], torrent_info["files"])

    torrent_files = [f for f in torrent_files if f.path[-1].endswith(video_ext)]

    if len(torrent_files) >= meta_info.episode_count:
        return title

    # now really fix title with episode

    episodes = set()
    for f in torrent_files:
        m = pattern_episodes.search(f.name)
        if not m:
            continue
        episodes.add(int(m.group("episode").lstrip("0")))

    if not episodes:
        return title

    start = min(episodes)
    end = max(episodes)
    if start == end:
        e = f"E{start:02d}"
    else:
        e = f"E{start:02d}-E{end:02d}"

    return pattern_season_only.sub(r"\1\2" + e + r"\3", title)


def _transform_info(obj: dict[bytes, Any]) -> dict[str, Any]:
    d = {}
    for key, value in obj.items():
        if key == b"pieces":
            d[key.decode()] = value
        else:
            d[key.decode()] = _transform_value(value)
    return d


def _transform_dict(obj: dict[bytes, Any]) -> dict[str, Any]:
    return {key.decode(): _transform_value(value) for key, value in obj.items()}


def _transform_value(v: Any) -> Any:
    if isinstance(v, bytes):
        try:
            return v.decode()
        except UnicodeDecodeError:
            return v
    if isinstance(v, dict):
        return _transform_dict(v)
    if isinstance(v, list):
        return [_transform_value(o) for o in v]
    return v


@dataclasses.dataclass(kw_only=True, slots=True)
class File:
    length: int
    path: Annotated[tuple[str, ...], annotated_types.MinLen(1)]

    @property
    def name(self) -> str:
        return self.path[-1]


@dataclasses.dataclass(kw_only=True, slots=False, frozen=True)
class TorrentInfo:
    name: Annotated[str, annotated_types.MinLen(1)]
    pieces: bytes
    length: int | None = None
    private: bool = False
    files: Annotated[tuple[File, ...], Field(default_factory=tuple)]
    piece_length: Annotated[int, Field(alias="piece length")]
    # common used field for private tracker
    source: str | None = None


@dataclasses.dataclass(kw_only=True, slots=True)
class Pick:
    title: str
    guid: str
    website: str
    link: str
    released_at: datetime
    size: int
    imdb_id: str = ""
    douban_id: str = ""


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class RssItem:
    title: str
    guid: str
    link: str
    size: int
    description: str = ""
    pub_date: datetime | None = None

    imdb_id: str | None = None
    douban_id: str | None = None


def parsedate_to_datetime(s: str | None) -> datetime:
    assert s, "empty pubDate"
    dt: datetime | None = _parsedate_to_datetime(s)
    if dt is None:
        raise ValueError(f"failed to parse pubDate as datetime {s}")
    return dt


pattern_douban_url = re.compile(r"https://movie\.douban\.com/subject/(\d+)/?")


def parse_rss_item(item: ElementTree.Element) -> RssItem:
    title = item.findtext("./title")
    assert title

    enclosure = item.find("./enclosure")
    assert enclosure is not None, "missing enclosure item"
    url = enclosure.attrib["url"]
    assert url

    guid = item.findtext("./guid")
    assert guid

    imdb_id = None
    imdb_el = item.find('./{http://torznab.com/schemas/2015/feed}attr[@name="imdb"]')
    if imdb_el:
        imdb_id = imdb_el.attrib["value"]

    description = item.findtext("./description") or ""

    douban_id = None
    if description:
        m = pattern_douban_url.search(description)
        if m:
            douban_id = m.group(1)

    pub_date = parsedate_to_datetime(item.findtext("pubDate"))

    return RssItem(
        title=title.strip(),
        guid=guid,
        link=url,
        pub_date=pub_date,
        description=description,
        size=int(enclosure.attrib.get("length", 0)),
        douban_id=douban_id,
        imdb_id=imdb_id,
    )


T = TypeVar("T")


def first(s: list[T], default: T) -> T:
    if s:
        return s[0]

    return default


class FailedToUploadImage(Exception):
    pass


def main() -> None:
    r = httpx.get(
        "https://prowlarr.omv.trim21.me/1/api?apikey=d56943ccd47344129f117f16e34c21b5&extended=1&t=search&q=mweb",
        timeout=40,
    )
    et = ElementTree.fromstring(r.content)
    for item_el in et.findall("channel/item"):
        item = parse_rss_item(item_el)
        print(item)

    #
    # cfg = load_config(pathlib.Path(__file__, "../../config.toml").resolve())
    #
    # app = Application.new(cfg)
    #
    # guid, website, title, link, released_at, size, douban_id, imdb_id = app.db.fetch_one(
    #     "select guid, website, title, link, released_at, size, douban_id, imdb_id from rss_item where title = $1",
    #     ["The Fiery Priest 2 S02E11 2024 1080p DSNP WEB-DL H264 AAC-ADWeb"],
    # )
    #
    # r = app.get_meta_info(
    #     Pick(
    #         guid=guid,
    #         website=website,
    #         title=title,
    #         link=link,
    #         released_at=released_at,
    #         size=size,
    #         douban_id=douban_id,
    #         imdb_id=imdb_id,
    #     )
    # )
    #
    # print(r)
    #


if __name__ == "__main__":
    main()
