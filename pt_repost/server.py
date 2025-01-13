from collections.abc import Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, AsyncGenerator, Protocol

import asyncpg
import fastapi
import orjson
from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse, JSONResponse

from pt_repost.config import load_config
from pt_repost.const import RSS_ITEM_STATUS_SKIPPED


class ORJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return orjson.dumps(content, option=orjson.OPT_INDENT_2)


class _Render(Protocol):
    def __call__(
        self,
        name: str,
        ctx: dict[str, Any] | None = ...,
        status_code: int = ...,
        headers: Mapping[str, str] | None = ...,
        media_type: str | None = ...,
    ) -> HTMLResponse: ...


templates = Jinja2Templates(directory=str(Path(__file__).parent.joinpath("templates").resolve()))


async def __render(request: Request) -> _Render:
    def render(
        name: str,
        ctx: dict[str, Any] | None = None,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            name=name,
            request=request,
            context=ctx,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
        )

    return render


Render = Annotated[_Render, Depends(__render)]


def create_app(config_file):
    cfg = load_config(config_file)

    pool = asyncpg.create_pool(cfg.pg_dsn())

    @asynccontextmanager
    async def lifespan(_app: fastapi.FastAPI) -> AsyncGenerator[None, None]:
        await pool
        yield
        await pool.close()

    app = fastapi.FastAPI(debug=cfg.debug, lifespan=lifespan)

    @app.get("/")
    async def index(render: Render) -> HTMLResponse:
        torrents = await pool.fetch(
            """select * from rss_item where status != $1 order by updated_at desc""",
            RSS_ITEM_STATUS_SKIPPED,
        )

        return render(
            "index.html.j2",
            ctx={"torrents": torrents},
        )

    @app.get("/{website}/{guid}")
    async def rss_item(website: str, guid: str, render: Render) -> HTMLResponse:
        torrent = await pool.fetchrow(
            """select * from rss_item where website = $1 and guid = $2""",
            website,
            guid,
        )

        return render(
            "rss-item.html.j2",
            ctx={"torrent": torrent},
        )

    return app
