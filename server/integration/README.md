# Isolated local integration dependencies

`../docker-compose-integration.yaml` is a separate dependency stack for local
integration testing. It defines MySQL, Redis, etcd, Kafka, and RustFS with an S3
compatible API, plus jobs that create the Kafka topics and buckets. It does not start the Go application or
any client. A valid Compose configuration is not evidence of working login,
messaging, upload, or client compatibility.

The Compose project is `chat-monorepo-public-integration`. Its default bridge network and
all five data volumes belong to that project. There are no fixed container names,
external resources, host network mode, or fixed subnets. Persistent state uses
named volumes; no existing host data directory is mounted. The only host bind is
the repository's SQL directory, mounted read-only to initialize a fresh database.
Initialization runs only when the MySQL volume is empty.

## Port registration is required before startup

This checkout's integration and application ports are registered on this Mac to
`Chat Monorepo Public Runtime` (project ID
`2da758a8f2dc45dfa04bbcee49b9dd8c`) at
`/Users/shiyi/Documents/clawchat/monorepo-public`. Recheck registration and
current listeners before each startup using the local port manager. The
registration is machine local; other machines need their own allocation.

| Service | Host endpoint | Endpoint inside this Compose project |
| --- | --- | --- |
| MySQL | `127.0.0.1:23316` | `mysql:3306` |
| Redis | `127.0.0.1:26389` | `redis:6379` |
| etcd | `127.0.0.1:22389` | `etcd:2379` |
| Kafka | `127.0.0.1:29012` | `kafka:9092` |
| RustFS S3 API | `127.0.0.1:29010` | `minio:9000` |
| RustFS console | `127.0.0.1:29011` | `minio:9001` |

All published ports bind to IPv4 loopback. Kafka has separate internal and host
listeners: its host port maps to container port `19092`, and metadata advertises
`127.0.0.1:29012` to host clients. Only services joined to this project's network
can use the container DNS names. The existing application Compose file is not
joined to this network, and launching it does not connect it to this stack.

## Prepare and validate without starting containers

Run the following from the monorepo root. Docker Compose is required; `config`
and the Python tests do not create containers, networks, or volumes.

```bash
cp server/integration/.env.example server/integration/.env
openssl rand -hex 32
```

Run `openssl rand -hex 32` separately for each secret and put the generated values
in `server/integration/.env`. Do not commit this file. The database and username
are both `teamgram`; the S3 username is `integration-minio`. The Compose file
requires all three passwords and does not inherit the original stack's password
variables.

```bash
docker compose --project-name chat-monorepo-public-integration \
  --env-file server/integration/.env \
  -f server/docker-compose-integration.yaml config --quiet
python3 -m unittest discover -s tests -v
```

The tests supply temporary test-only credentials and validate the resolved
configuration: isolated resource ownership, named data volumes, read-only host
mounts, distinct loopback mappings, and Kafka listener addresses. Never use those
test-only credentials to start services.

## Start and inspect this project after registration

Use the same project name, env file, and Compose file on every command; do not
merge this file with the existing application or environment Compose files.
Check that the six dependency ports are registered to this checkout and free,
then start the dependencies:

```bash
python3 /Users/shiyi/Documents/ChatGPT/duankou/portctl.py check \
  --project 2da758a8f2dc45dfa04bbcee49b9dd8c \
  --ports 22389,23316,26389,29010,29011,29012
docker compose --project-name chat-monorepo-public-integration \
  --env-file server/integration/.env \
  -f server/docker-compose-integration.yaml up -d
docker compose --project-name chat-monorepo-public-integration \
  --env-file server/integration/.env \
  -f server/docker-compose-integration.yaml ps -a
docker compose --project-name chat-monorepo-public-integration \
  --env-file server/integration/.env \
  -f server/docker-compose-integration.yaml logs --tail 100
```

Check that MySQL, Redis, etcd, Kafka, and RustFS report healthy and that
`kafka-init` and `minio-init` exit with code zero. Check S3 readiness with
`curl --fail http://127.0.0.1:29010/health`. Setup jobs fail if topic or bucket
creation fails. Inspect this project's logs if a job fails.

The intended volumes are `chat-monorepo-public-integration_mysql_data`,
`chat-monorepo-public-integration_redis_data`,
`chat-monorepo-public-integration_etcd_data`,
`chat-monorepo-public-integration_kafka_data`, and
`chat-monorepo-public-integration_minio_data`. The intended network is
`chat-monorepo-public-integration_default`. Inspect their
ownership before reusing a project name from an earlier run.

## Stop while preserving integration data

```bash
docker compose --project-name private-chat-integration \
  --env-file server/integration/.env \
  -f server/docker-compose-integration.yaml down
```

`down` removes this project's containers and network and preserves its named
data volumes. Do not add `--volumes` or run global Docker cleanup commands unless
deleting integration data has been separately authorized. Do not release the
registered ports merely because the services are stopped.

## Remaining validation

The object store uses RustFS 1.0.4 and its `rc` 0.1.30 client pinned by image
digest. The Compose service and volume keep the name `minio` for compatibility
with the Go service's MinIO S3 client. SQL initialization uses the repository's
existing schema and migrations; actual application behavior still needs testing.

See `LOCAL_RUNTIME.md` for isolated Go service configuration, foreground startup,
and local file verification codes. No SMS provider or signing credentials are
needed for that explicit local mode.
