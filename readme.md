## 安装

确保当前机器安装了 ffmpeg 和 mediainfo, 以及 python >= 3.10。

使用 pip 或者 pipx 命令安装

```shell
pipx install https://github.com/trim21/pt-repost/archive/refs/heads/master.zip
```

## 使用

参照 `config.example.toml` 在 **当前工作路径** 下创建 `config.toml` 文件。

填写 `qb-url` 和对应站点的 cookies。

确保具体任务在QB中已经下载完。

从下载完成的qb种子种复制 "Torrent Hash" 或者 "信息哈希值 v1" (同一个东西，不同版本的 qb 的UI不一样)

使用 `pt-repost info_hash douban-id` 发种。

比如 `pt-repose e5031a8c4a759fa5fc591b54750e7ca260bc443e 36582628`
