create table if not exists imdb (
    id text not null,
    season int not null default 1,
    douban_id text not null,
    douban_info text not null,
    primary key (id, season)
);
