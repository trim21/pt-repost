FROM rust:1-bullseye@sha256:d67c1c879418037577d2b7cc6ae9d128453185c308de42517fd5d3644c7f5e04 AS oxipng

RUN cargo install oxipng

FROM ghcr.io/astral-sh/uv:python3.10-bookworm@sha256:91129296fcfd6201ad611f114af87a64a32354a2e460c94af6ea438a997652c1 AS uv

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

COPY --from=oxipng /usr/local/cargo/bin/oxipng /usr/local/bin/oxipng
# check oxipng is working
RUN oxipng --version

COPY --from=uv /app/requirements.txt .

RUN pip install --only-binary=:all: --no-cache -r requirements.txt

COPY . .
