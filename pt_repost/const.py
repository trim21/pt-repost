from typing import Final

LOCK_KEY_SCHEDULE_RSS: Final = "schedule"
LOCK_KEY_PICK_RSS_JOB: Final = "pick-rss-job"

# status of rss_run
TASK_STATUS_PENDING: Final = "pending"
TASK_STATUS_RUNNING: Final = "running"
TASK_STATUS_SUCCESS: Final = "success"
TASK_STATUS_FAILED: Final = "failed"

# status of rss_item
RSS_ITEM_STATUS_PENDING: Final = "pending"
RSS_ITEM_STATUS_SKIPPED: Final = "skipped"
RSS_ITEM_STATUS_DOWNLOADING: Final = "downloading"  # 下载中
RSS_ITEM_STATUS_UPLOADING: Final = "uploading"  # 已发帖
RSS_ITEM_STATUS_DONE: Final = "done"  # 已出种
RSS_ITEM_STATUS_REMOVED_FROM_SITE: Final = "removed-by-site"  # 被站点删除
RSS_ITEM_STATUS_REMOVED_FROM_DOWNLOAD_CLIENT: Final = "removed-by-client"  # 被从客户端删除
RSS_ITEM_STATUS_FAILED: Final = "failed"

RSS_ITEM_STATUS_PROCESSING: Final = (
    RSS_ITEM_STATUS_DOWNLOADING,
    RSS_ITEM_STATUS_UPLOADING,
)

SSD_REMOVED_MESSAGE: Final = "Torrent not registered with this tracker"

DEFAULT_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        + " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    )
}


QB_CATEGORY = "pt-repost"
