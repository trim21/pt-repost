import abc
import re
from http.cookies import SimpleCookie
from typing import Any

import bencode2
import guessit
import httpx

from app.config import config
from app.mediainfo import MediaInfo
from app.meta_info import Info, Region

pattern_dovi = re.compile(r"\bDolby Vision\b", re.IGNORECASE)
pattern_hdr10 = re.compile(r"\bHDR10\b", re.IGNORECASE)
pattern_hdr10_plus = re.compile(r"[ /,]HDR10\+[ /,]", re.IGNORECASE)
pattern_hdr10_vivid = re.compile(r"\bHDR Vivid\b", re.IGNORECASE)


class Website(abc.ABC):
    @abc.abstractmethod
    def parse_mediainfo_as_options(
        self, filename: str, m: MediaInfo
    ) -> dict[str, Any]: ...


class SSD(Website):
    def parse_mediainfo_as_options(self, filename: str, m: MediaInfo) -> dict[str, Any]:
        options: dict[str, Any] = {}

        guess: dict[str, str] = guessit.guessit(filename)

        match guess.get("type"):
            case "movie":
                options["type"] = "501"
            case "episode":
                options["type"] = "502"
            case _:
                options["type"] = "509"

        if "source" in guess:
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
            if guess["source"] in medium_options:
                options["medium_sel"] = medium_options[guess["source"]]
            else:
                raise NotImplementedError()
        else:
            raise NotImplementedError()

        match m.video[0].width:
            case 3840:  # 2160
                options["standard_sel"] = 1
            case 1920:  # 1080
                if "1080i" in filename.lower():
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
            raise NotImplementedError(
                f"failed to find audiocodec_sel for {m.audio[0].format!r}"
            )

        for track in m.video:
            if track.hdr_format_string:
                if pattern_dovi.search(track.hdr_format_string):
                    options["dovi"] = "1"
                if pattern_hdr10.search(track.hdr_format_string):
                    options["hdr10"] = "1"
                if pattern_hdr10_plus.search(track.hdr_format_string):
                    options["hdr10plus"] = "1"
                if pattern_hdr10_vivid.search(track.hdr_format_string):
                    options["hdrvivid"] = "1"

        for text in m.text:
            lang = text.language.lower()
            title = text.title.lower()
            for word in {"zh-cn", "zh-cn", "zh-cn", "chinese", "cmn-hans", "cmn-hant"}:
                if word in lang or word in title:
                    options["subtitlezh"] = "1"
                    break

        return options

    region_options = {
        "Mainland": 1,
        "Hongkong": 2,
        "Taiwan": 3,
        "West": 4,
        "Japan": 5,
        "Korea": 6,
        "India": 7,
        "Russia": 8,
        "Thailand": 9,
        "Other": 99,
    }

    def create_post(
        self,
        torrent: bytes,
        mediainfo_text: str,
        url: str,
        images: list[str],
        options: dict[str, Any],
        info: Info,
    ):
        data = options | {
            # douban/imdb url
            "name": bencode2.bdecode(torrent)[b"info"][b"name"].decode(),
            "small_descr": info.subtitle,  # 副标题
            "url": url,
            "url_vimages": "\n".join(images),
            "url_poster": "",
            "qr_check": "ok",
            "Media_BDInfo": mediainfo_text,
            "descr": "",
            "offer": "yes",  # 候选区
        }

        match info.region:
            case Region.Mainland:
                data["source_sel"] = 1
            case Region.HK:
                data["source_sel"] = 2
            case Region.TW:
                data["source_sel"] = 3
            case Region.USA | Region.UK:
                data["source_sel"] = 4
            case _:
                raise NotImplementedError(f"not supported region {info.region.name}")

        cookie = SimpleCookie()
        cookie.load(config.website.ssd.cookies)

        res = httpx.post(
            "https://springsunday.net/takeupload.php",
            files={"file": ("a.torrent", torrent)},
            data=data,
            headers={
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                )
            },
            cookies={k: v.value for k, v in cookie.items()},
        )

        print(res.status_code)
        if res.is_redirect:
            print(res.headers.get("location"))
        print(res.text)
