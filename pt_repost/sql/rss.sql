create table if not exists rss
(
    id serial primary key not null,
    url text not null,
    exclude_url text not null default '',
    website text not null,
    includes json not null,
    excludes json not null,
    interval_seconds int4 not null default 600
);

create table if not exists rss_run
(
    id serial8 primary key not null,
    rss_id int4 not null,
    node_id text not null,
    created_at timestamptz not null,
    status text not null,
    failed_reason text not null default ''
);

create table if not exists tmdb_info
(
    title text primary key not null,
    tmdb_id int8 not null,
    tmdb_type text not null
);
