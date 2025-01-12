create table if not exists image (
    info_hash text not null,
    uuid uuid not null default gen_random_uuid(),
    url text,
    primary key (info_hash, uuid)
);
