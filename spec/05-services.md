# Services: any database, queue or index the system needs

The architecture is the agent's. There is no menu: any open-source software from a
public image works — Postgres, MySQL, MongoDB, Redis, Valkey, RabbitMQ, NATS, Kafka,
Meilisearch, Typesense, OpenSearch, MinIO, ClickHouse, Qdrant, Ollama, anything else.

Often the right answer is nothing extra: SQLite and the platform's links already carry a
lot. The choice is made by what the product needs.

Services go in the system's `compose.yaml`, written the way anyone writes one:

```yaml
services:
  db:                                  # the name is its address: programs reach it at db:5432
    image: postgres:16-alpine          # any public image (Docker Hub, ghcr.io, quay.io)
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: a-long-random-password
      POSTGRES_DB: app
    volumes: ["db-data:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER"]   # $$ is the container's own variable
      interval: 5s
    mem_limit: 1g                      # default 512m, up to 2g
    cpus: 0.5                          # default 0.5, up to 1
    x-bnome:                           # what only Bnome reads
      description: Orders, stock and invoices     # what the owner reads on the canvas
      provides:                        # environment every program of the system gets
        DATABASE_URL: postgresql://app:a-long-random-password@db:5432/app
      internet: false                  # true if the service itself must reach the internet
  cache:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes: ["cache-data:/data"]
    depends_on: {db: {condition: service_healthy}}
    x-bnome:
      provides: {REDIS_URL: "redis://cache:6379/0"}
      views:                           # what the owner sees when they open this service
        - name: Photos waiting
          run: ["redis-cli", "LRANGE", "photos:waiting", "0", "99"]
volumes:
  db-data: {}
  cache-data: {}
```

Bnome reads compose's own keys — `image`, `command`, `entrypoint`, `environment`,
`volumes` (a named volume, or `/shared:/path`), `healthcheck`, `depends_on`
(`service_started` or `service_healthy`), `mem_limit`, `cpus` (or
`deploy.resources.limits`), `user`, `working_dir`, `labels`, `tmpfs`, `shm_size`,
`init`, `stop_signal`. `restart` and `expose` change nothing: the platform always starts
a service again, and on the system's network every port is reachable.

## The `x-bnome` keys

| | |
|---|---|
| `description` | one line, what this is for, in the owner's words |
| `provides` | environment every program of the system gets; programs restart when it changes, so an address or a password is never written into code |
| `internet` | `true` only if the service itself must reach out |
| `views` | what the owner sees inside the service: a `name` in their words and a `run` command the platform runs inside it. Its output becomes a table — JSON, one JSON value per line, CSV or TSV with a header, `key: value` lines, or plain lines; set `format` when it is not obvious. A view runs whenever the owner looks, so it only reads and finishes in seconds. |

Postgres shows its tables by itself; Redis and Valkey, MySQL and MariaDB, MongoDB and
RabbitMQ each get an overview of their own. Declare `views` for what matters in *this*
product: the photos waiting, the search index, the messages in a stream.

## Not available, because the server stays safe

`privileged`, `cap_add`, `devices`; `ports` on the server, host paths, `networks`;
`build` — the system's own code runs in programs and their workers.

Only this system's programs reach a service. It has no way out unless `internet: true`.

## From your agent

`describe_system` lists every service with its image, status, size and which programs
use it, and lists every database at `data[]` — including the service ones, with their
tables, which `read_table` and `query_data` then read.

Declaring or changing a service is code: ask `ask_bnome_agent` for the outcome
("orders need full-text search over 2M rows"), not for a specific image.
