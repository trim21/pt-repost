启动单机版本

```yaml
networks:
  pt-repost:

services:
  pg:
    image: postgres:16
    restart: always
    networks: [pt-repost]
    command:
      - -c
      - max_connections=1000
    environment:
      - POSTGRES_USER=pt-repost
      - POSTGRES_PASSWORD=your-password
      - POSTGRES_DB=pt-repost
    ports:
      - "5432:5432"
    volumes:
      - ./data/pg:/var/lib/postgresql/data
  pt-repost-daemon:
    image: "ghcr.io/trim21/pt-repost:daemon"
    networks: [pt-repost]
    command:
      - daemon
      - --config-file=/etc/pt-repost/config.toml
    volumes:
      # 必需要把 qBittorrent 的下载路径原样 mount
      # 否则会出现找不到文件的错误
      - /downloads/:/downloads/
      - ./config.toml:/etc/pt-repost/config.toml
  pt-repost-ui:
    image: "ghcr.io/trim21/pt-repost:daemon"
    networks: [pt-repost]
    command:
      - server
      - --config-file=/etc/pt-repost/config.toml
      - --port=8080
      - --host=0.0.0.0
    ports:
      - "8080:8080"
    volumes:
      - ./config.toml:/etc/pt-repost/config.toml
```

daemon 可以在多节点上运行，需要使用 tailscale 等工具组网。
