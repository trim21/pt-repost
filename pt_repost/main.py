import click
import uvicorn

from pt_repost.application import Application
from pt_repost.config import load_config
from pt_repost.server import create_app


@click.group()
def cli() -> None: ...


@cli.command()
@click.option(
    "--config-file",
    "config_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
)
def daemon(config_file: str) -> None:
    cfg = load_config(config_file)

    app = Application.new(cfg)

    app.start()


@cli.command()
@click.option(
    "--config-file",
    "config_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
)
@click.option("--port", default=8080)
@click.option("--host", default="127.0.0.1")
def server(config_file: str, port: int, host: str) -> None:
    uvicorn.run(lambda: create_app(config_file), port=port, host=host)
