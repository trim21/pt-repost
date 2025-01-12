create table if not exists mediainfo(
    info_hash text primary key,
    mediainfo_text text not null,
    mediainfo_json text not null
)
