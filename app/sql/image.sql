create table if not exists image (
    image_id integer primary key autoincrement,
    task_id integer,
    url text
);
