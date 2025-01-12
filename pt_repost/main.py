import click

from pt_repost.application import Application
from pt_repost.config import load_config


@click.command()
@click.option(
    "--config-file-location",
    "config_file_location",
    default=None,
)
def main(config_file_location: str) -> None:
    cfg = load_config(config_file_location)

    app = Application.new(cfg)

    app.start()
