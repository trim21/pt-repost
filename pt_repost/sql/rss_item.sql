create table if not exists rss_item
(
    guid text not null,
    website text not null,
    title text not null,
    link text not null,
    released_at timestamptz not null default current_timestamp,
    size int8 not null,
    status text not null,
    updated_at timestamptz not null default current_timestamp,
    picked_node text not null default '',
    info_hash text not null default '', -- hex lower case
    process_status text not null default '',
    progress double precision not null default 0,
    hard_code_chinese_subtitle bool not null default false,
	failed_reason text default '' not null,
	meta_info text not null default '',
    target_info_hash text not null default '',

    douban_id text not null default '',
    imdb_id text not null default '',

    primary key (guid, website)
);
