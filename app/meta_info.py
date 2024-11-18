import dataclasses
import enum
import re

import httpx


class Region(enum.IntEnum):
    Mainland = 0
    USA = 1
    HK = 2
    TW = 3
    UK = 4


@dataclasses.dataclass(frozen=True, slots=True)
class Info:
    region: Region
    subtitle: str


pattern_region = re.compile(r"◎产\W+地\W+(.+?)\n")
pattern_subtitle = re.compile(r"◎译\W+名\W+(.+?)\n")


def match_region(info: str) -> Region:
    m = pattern_region.search(info)
    if not m:
        raise ValueError("failed to find region")

    region = m.group(1)

    if "美国" in region:
        return Region.USA

    match region:
        case "英国":
            return Region.UK
        case "中国大陆":
            return Region.Mainland

    raise NotImplementedError("unknown region", region)


def extract_meta_info(douban_id: str):
    res = httpx.get(
        "https://api.iyuu.cn/App.Movie.Ptgen",
        params={"url": f"https://movie.douban.com/subject/{douban_id}/"},
    )
    data = res.json()

    if data["ret"] != 200:
        raise Exception("failed to get info from PT-Gen", data)

    s: str = data["data"]["format"]

    subtitle = pattern_subtitle.search(s)
    if not subtitle:
        raise ValueError(f"failed to find subtitle from PTGen-info {s!r}")

    return Info(region=match_region(s), subtitle=subtitle.group(1))


if __name__ == "__main__":
    print(extract_meta_info("34805730"))
