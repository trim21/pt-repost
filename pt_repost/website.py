import abc
import re
from http.cookies import SimpleCookie
from typing import Any

import guessit
import httpx
import yarl

from pt_repost.config import Config
from pt_repost.mediainfo import MediaInfo
from pt_repost.tmdb import FullSubjectInfo
from pt_repost.utils import dedupe

pattern_dovi = re.compile(r"\bDolby Vision\b", re.IGNORECASE)
pattern_hdr10 = re.compile(r"\bHDR10\b", re.IGNORECASE)
pattern_hdr10_plus = re.compile(r"\bHDR10\+\b", re.IGNORECASE)
pattern_hdr10_vivid = re.compile(r"\bHDR Vivid\b", re.IGNORECASE)


class Website(abc.ABC):
    @abc.abstractmethod
    def parse_mediainfo_as_options(self, filename: str, m: MediaInfo) -> dict[str, Any]: ...


class SSD(Website):
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def parse_mediainfo_as_options(self, release_name: str, m: MediaInfo) -> dict[str, Any]:
        options: dict[str, Any] = {}

        guess: dict[str, Any] = guessit.guessit(release_name)

        if "season" in guess and "episode" not in guess:
            options["pack"] = "1"

        match guess.get("type"):
            case "movie":
                options["type"] = "501"
            case "episode":
                options["type"] = "502"
            case _:
                options["type"] = "509"

        medium_options = {
            "Blu-ray": 1,
            "Remux": 4,
            "MiniBD": 2,
            "BDRip": 6,
            "WEB-DL": 7,
            "Web": 7,
            "WEBRip": 8,
            "HDTV": 5,
            "TVRip": 9,
            "DVD": 3,
            "DVDRip": 10,
            "CD": 11,
            "Other": 99,
        }

        options["medium_sel"] = medium_options.get(guess.get("source", "Other"), 99)

        match m.video[0].width:
            case 3840:  # 2160
                options["standard_sel"] = 1
            case 1920:  # 1080
                if "1080i" in release_name.lower():
                    options["standard_sel"] = 3
                else:
                    options["standard_sel"] = 2
            case _:
                raise NotImplementedError()

        match m.video[0].format:
            case "HEVC":
                options["codec_sel"] = 1
            case "AVC":
                options["codec_sel"] = 2
            case _:
                raise NotImplementedError()

        audio_codec = {
            "DTS-HD": 1,
            "TrueHD": 2,
            "LPCM": 6,
            "DTS": 3,
            "E-AC-3": 11,
            "AC-3": 4,
            "AAC": 5,
            "FLAC": 7,
            "APE": 8,
            "WAV": 9,
            "MP3": 10,
            "Other": 99,
        }
        audio_format = m.audio[0].format
        if audio_format in audio_codec:
            options["audiocodec_sel"] = audio_codec[audio_format]
        else:
            raise NotImplementedError(f"failed to find audiocodec_sel for {m.audio[0].format!r}")

        for track in m.video:
            for fmt in [
                track.hdr_format_string,
                track.hdr_format,
                track.hdr_format_compatibility,
            ]:
                if fmt:
                    if pattern_dovi.search(fmt):
                        options["dovi"] = "1"
                    if pattern_hdr10.search(fmt) and not pattern_hdr10_plus.search(fmt):
                        options["hdr10"] = "1"
                    if pattern_hdr10_plus.search(fmt):
                        options["hdr10plus"] = "1"
                    if pattern_hdr10_vivid.search(fmt):
                        options["hdrvivid"] = "1"

        for text in m.text:
            language_string = text.language_string.lower()
            lang = text.language.lower()
            title = text.title.lower()
            if any(
                ((word in lang) or (word in title) or ("chinese" in language_string))
                for word in {
                    "zh",
                    "zh-cn",
                    "chinese",
                    "cmn-hans",
                    "cmn-hant",
                }
            ):
                options["subtitlezh"] = "1"
                break

        return options

    def create_post(
        self,
        torrent: bytes,
        release_name: str,
        mediainfo_text: str,
        images: list[str],
        options: dict[str, Any],
        info: FullSubjectInfo,
    ) -> bytes:
        sub_title = " / ".join(dedupe([t for t in info.names if t]))

        data: dict[str, Any] = options | {
            "name": release_name.replace(" ", "."),
            "small_descr": sub_title,
            "url": (
                f"https://movie.douban.com/subject/{info.douban_id}/"
                if info.douban_id
                else f"https://www.imdb.com/title/{info.imdb_id}"
            ),
            "url_vimages": "\n".join(images),
            "url_poster": "",
            "qr_check": "ok",
            "Media_BDInfo": mediainfo_text,
            "descr": "",
            "offer": "yes",  # 候选区
        }

        # region_options = {
        #     'Thailand': 9,
        # }

        if "CN" in info.origin_country:
            data["source_sel"] = 1
        elif "HK" in info.origin_country:
            data["source_sel"] = 2
        elif "TW" in info.origin_country:
            data["source_sel"] = 3
        elif {"US", "BE", "FR"} & set(info.origin_country):
            data["source_sel"] = 4
        elif "JP" in info.origin_country:
            data["source_sel"] = 5
        elif "KR" in info.origin_country:
            data["source_sel"] = 6
        elif "IN" in info.origin_country:
            data["source_sel"] = 7
        elif "RU" in info.origin_country:
            data["source_sel"] = 8
        else:
            data["source_sel"] = 99

        if 16 in info.genre_ids:
            data["animation"] = 1
        if 99 in info.genre_ids:
            data["type"] = "503"

        cookie = SimpleCookie()
        cookie.load(self.cfg.website.ssd.cookies)

        with httpx.Client(
            headers={
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    + "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                )
            },
            cookies={k: v.value for k, v in cookie.items()},
        ) as client:
            res = client.post(
                "https://springsunday.net/takeupload.php",
                files={"file": ("a.torrent", torrent)},
                data=data,
                headers={
                    "user-agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        + "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                    )
                },
                cookies={k: v.value for k, v in cookie.items()},
            )

            if not res.is_redirect:
                raise Exception("failed to create post {!r}".format(res.text))

            redirect_url = "https://springsunday.net" + res.headers.get("location")
            thread_id = yarl.URL(redirect_url).query["id"]
            res = client.get(
                f"https://springsunday.net/download.php?id={thread_id}&passkey={self.cfg.website.ssd.passkey}"
            )
            if res.is_error:
                if '<td class="text">该种子已存在！' in res.text:
                    raise Exception("种子已存在")
                raise Exception("failed to download torrent {!r}".format(res.text))

            return res.content
