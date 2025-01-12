create table if not exists node
(
    id text primary key not null,
    last_seen timestamptz not null
);
