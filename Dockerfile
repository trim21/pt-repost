FROM rust:1-bullseye AS rust-build

RUN cargo install oxipng

FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    mediainfo &&\
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./requirements.prod.txt /app/requirements.txt

ENV PIP_ROOT_USER_ACTION=ignore

RUN pip install --only-binary=:all: --no-cache -r requirements.txt

COPY --from=rust-build /usr/local/cargo/bin/oxipng /usr/local/bin/oxipng
# check oxipng is working
RUN oxipng --version

COPY . .

ENTRYPOINT ["python", "main.py"]
