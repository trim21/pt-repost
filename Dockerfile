FROM rust:1-bullseye@sha256:1e3f7a9fd1f278cc4be02a830745f40fe4b22f0114b2464a452c50273cc1020d AS rust-build

RUN cargo install oxipng

FROM ghcr.io/astral-sh/uv:python3.10-bookworm AS build

WORKDIR /app

COPY uv.lock pyproject.toml ./

RUN uv export --no-group dev --locked --no-build --no-emit-project > /app/requirements.txt

FROM python:3.10-slim@sha256:66aad90b231f011cb80e1966e03526a7175f0586724981969b23903abac19081

WORKDIR /app
ENV PIP_ROOT_USER_ACTION=ignore \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

ENTRYPOINT ["python", "main.py"]

RUN apt-get update && apt-get install -y ffmpeg mediainfo &&\
    rm -rf /var/cache/apt/archives /var/lib/apt/lists/*

COPY --from=rust-build /usr/local/cargo/bin/oxipng /usr/local/bin/oxipng
# check oxipng is working
RUN oxipng --version

COPY --from=build /app/requirements.txt .

RUN pip install --only-binary=:all: --no-cache -r requirements.txt

COPY . .
