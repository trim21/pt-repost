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
    image: ...
    networks: [pt-repost]
    command:
      - daemon
    # 必需要把qb的下载路径mount进去
    volumes:
      - /srv/:/srv/
  pt-repost-ui:
    image: ...
    networks: [pt-repost]
    command:
      - server
      - --port=8080
      - --host=0.0.0.0
    ports:
      - '8080:8080'
```
