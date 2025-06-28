FROM rust:1-bullseye@sha256:eb809362961259a30f540857c3cac8423c466d558bea0f55f32e3a6354654353 AS oxipng

RUN cargo install oxipng

FROM ghcr.io/astral-sh/uv:python3.10-bookworm@sha256:8c1a5a88e4334d96c60efda40a001973a6f1b3ea4b90fc2950b6bc39cfa18fb7 AS uv

WORKDIR /app

COPY uv.lock pyproject.toml ./

RUN uv export --no-group dev --locked --no-build --no-emit-project > /app/requirements.txt

FROM python:3.10-slim@sha256:57038683f4a259e17fcff1ccef7ba30b1065f4b3317dabb5bd7c82640a5ed64f

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
