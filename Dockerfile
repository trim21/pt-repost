FROM rust:1-bullseye as rust-build

RUN cargo install cargo-binstall && \
    cargo binstall oxipng

FROM ghcr.io/astral-sh/uv:debian-slim AS build

WORKDIR /app

COPY uv.lock pyproject.toml ./

RUN uv export --no-group dev --locked --no-emit-project > /app/requirements.txt

FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    mediainfo &&\
    rm -rf /var/lib/apt/lists/*

COPY --from=rust-build /root/.local/oxipng /usr/local/bin/oxipng

RUN oxipng --help

WORKDIR /app

COPY --from=build /app/requirements.txt .

ENV PIP_ROOT_USER_ACTION=ignore

RUN pip install --only-binary=:all: --no-cache -r requirements.txt

COPY . .

ENTRYPOINT ["python", "main.py"]
