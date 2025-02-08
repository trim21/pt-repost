FROM rust:1-bullseye@sha256:1e3f7a9fd1f278cc4be02a830745f40fe4b22f0114b2464a452c50273cc1020d AS rust-build

RUN cargo install oxipng

FROM ghcr.io/astral-sh/uv:debian-slim@sha256:3ac4e2ef46fd5a0fb0cf5af9a421435513fec1b2a66e1379a7981dc03470fd33 AS build

WORKDIR /app

COPY uv.lock pyproject.toml ./

RUN uv export --no-group dev --frozen --no-emit-project > /app/requirements.txt

FROM python:3.10-slim

WORKDIR /app
ENV PIP_ROOT_USER_ACTION=ignore

ENTRYPOINT ["python", "main.py"]

RUN apt-get update && apt-get install -y ffmpeg mediainfo &&\
    rm -rf /var/cache/apt/archives /var/lib/apt/lists/*

COPY --from=rust-build /usr/local/cargo/bin/oxipng /usr/local/bin/oxipng
# check oxipng is working
RUN oxipng --version

COPY --from=build /app/requirements.txt .

RUN pip install --only-binary=:all: --no-cache -r requirements.txt

COPY . .
