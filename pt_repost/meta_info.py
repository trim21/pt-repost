import html

import httpx


def generate_thread_description(imdb_id: str) -> str:
    res = httpx.get(
        "https://api.iyuu.cn/App.Movie.Ptgen",
        params={"url": imdb_id},
    )
    data = res.json()

    if data["ret"] != 200:
        raise Exception("failed to get info from PT-Gen", data)

    return html.unescape(data["data"]["format"])
