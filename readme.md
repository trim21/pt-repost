从最新的 [github actions](https://github.com/trim21/pt-repost/actions/workflows/build.yaml)
下载可执行文件，解压到本地。

确保当前机器安装了 ffmpeg 和 mediainfo。

参照 `config.example.toml` 在 **当前工作路径** 下创建 `config.toml` 文件夹

填写 `qb-url` 和对应站点的 cookies。

确保具体任务在QB中已经下载完。

使用 `pt-repost info_hash douban-id` 发种。

比如 `pt-repose e5031a8c4a759fa5fc591b54750e7ca260bc443e 36582628`
