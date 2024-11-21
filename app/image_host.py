import uuid
from pathlib import Path

import httpx
import yarl
from sslog import logger

from app.config import Config


class FailedToUploadImage(Exception):
    pass


def upload(file: Path, site: str, config: Config) -> str:
    return upload_pixhost(file, config)
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


def upload_pixhost(file: Path, config: Config) -> str:
    logger.debug("upload image {} size {}", file, file.lstat().st_size)
    http_client = httpx.Client(proxy=config.http_proxy)

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
