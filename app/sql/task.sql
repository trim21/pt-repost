create table if not exists task
(
    task_id   integer primary key autoincrement,
    info_hash varchar(64),
    site      varchar(10),
    status    integer,
    title     text,
    sub_title text,
    douban_id integer      default '' not null,
    imdb_id   varchar(255) default '' not null,
    tmdb_id   varchar(255) default '' not null,
    unique (info_hash, site) on conflict abort
);
