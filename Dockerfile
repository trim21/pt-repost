FROM ghcr.io/astral-sh/uv:debian-slim AS build

WORKDIR /app

COPY uv.lock pyproject.toml ./

RUN uv export --no-extra dev --locked --no-emit-project > /app/requirements.txt

FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    mediainfo &&\
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=build /app/requirements.txt .

RUN pip install --no-cache -r requirements.txt

COPY . .

ENTRYPOINT ["python", "main.py"]
