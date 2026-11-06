# Local Go runtime

This runs the backend on this Mac using the isolated integration dependencies.
It generates private runtime copies of the existing Go service configurations,
uses the local file verification-code provider, and leaves the checked-in
configuration files unchanged. It also generates a fresh 2048-bit RSA key in the
private runtime directory instead of relying on a shared repository key. It
does not launch a desktop, Android, or iOS client, and backend startup alone
does not establish multi-client end-to-end login, messaging, or upload
compatibility. No real SMS service is used.

## Dependency stack

Follow [README.md](README.md) to create `server/integration/.env` and validate the
separate `chat-monorepo-public-integration` Compose project. The runtime runner does not
start Docker, import data from another stack, or stop existing containers. Start
and inspect only the integration project, from the monorepo root:

```bash
docker compose --project-name chat-monorepo-public-integration \
  --env-file server/integration/.env \
  -f server/docker-compose-integration.yaml up -d
docker compose --project-name chat-monorepo-public-integration \
  --env-file server/integration/.env \
  -f server/docker-compose-integration.yaml ps -a
```

Wait for MySQL, Redis, etcd, Kafka, and the S3 service to report healthy, and for
`kafka-init` and `minio-init` to exit with status zero. Inspect this project's
logs if initialization fails; a MySQL container health check can pass even when
schema initialization failed. Confirm the database initialization log completed
and the expected `teamgram` tables and migrations exist before starting Go. Do
not restart or remove a different project's services to clear a port conflict.

The Go runtime connects to these host endpoints:

| Dependency | Endpoint |
| --- | --- |
| MySQL | `127.0.0.1:23316` |
| Redis | `127.0.0.1:26389` |
| etcd | `127.0.0.1:22389` |
| Kafka | `127.0.0.1:29012` |
| S3 API | `127.0.0.1:29010` |

etcd also advertises `http://127.0.0.1:22389` to host clients, so automatic
endpoint synchronization keeps using the host-accessible loopback address.

## Build and verify

Use the Go version required by `server/go.mod` or a compatible newer toolchain.
The currently installed Mac ARM64 toolchain is Go 1.26.8 at
`/Users/shiyi/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.8.darwin-arm64/bin`.
The local command, from `/Users/shiyi/Documents/clawchat/monorepo-public/server`, is:

```bash
PATH=/Users/shiyi/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.8.darwin-arm64/bin:$PATH make -j4 all
```

The `all` target builds the eleven service executables in `teamgramd/bin`. It
does not build or start `httpserver`. From the monorepo root, validate the Python
runtime behavior and isolated Compose contract without starting application
services:

```bash
python3 -m unittest server.integration.test_local_runtime server.integration.test_run_local -v
python3 -m unittest discover -s tests -v
```

## Registered ports and foreground startup

The application and integration ports below are registered on this Mac to
`Chat Monorepo Public Runtime`, project ID `2da758a8f2dc45dfa04bbcee49b9dd8c`,
with canonical directory `/Users/shiyi/Documents/clawchat/monorepo-public`.
Other machines must allocate and configure their own ports in
`server/integration/.env`.

| Registered endpoint | Loopback port |
| --- | --- |
| gnet MTProto TCP | `35222` |
| gnet WebSocket | `35443` |
| BFF gRPC | `36010` |
| biz gRPC | `36020` |
| msg gRPC | `36030` |
| gnetway gRPC | `36110` |
| session gRPC | `36120` |
| sync gRPC (reserved; inactive) | `36420` |
| authsession gRPC | `36450` |
| DFS gRPC | `36640` |
| media gRPC | `36650` |
| idgen gRPC | `36660` |
| status gRPC | `36670` |
| DFS media HTTP | `37701` |

The `sync` process runs as a Kafka consumer. Its gRPC server setup is disabled
in the current source, so the process remains alive without listening on the
reserved port `36420`.

Recheck registration and current listeners before every startup. The port
manager also rechecks before its managed launch:

```bash
python3 /Users/shiyi/Documents/ChatGPT/duankou/portctl.py check \
  --project 2da758a8f2dc45dfa04bbcee49b9dd8c \
  --ports 35222,35443,36010,36020,36030,36110,36120,36420,36450,36640,36650,36660,36670,37701
python3 /Users/shiyi/Documents/ChatGPT/duankou/portctl.py run \
  --project 2da758a8f2dc45dfa04bbcee49b9dd8c \
  --ports 35222,35443,36010,36020,36030,36110,36120,36420,36450,36640,36650,36660,36670,37701 \
  -- python3 /Users/shiyi/Documents/clawchat/monorepo-public/server/integration/run_local.py
```

The runner keeps all service children in its foreground process group, logs
each child's output under `server/integration/.runtime/logs`, and uses
`server/integration/.runtime` as their working directory. The BFF reads the
generated `config.json` there. Its `dc_options` advertises only the ordinary
MTProto TCP endpoint at `127.0.0.1:35222`; the gateway also listens on
`[::1]:35222` for Desktop's IPv6 loopback option. WebSocket clients need their
own explicit WebSocket transport configuration. Go-zero development listeners
are disabled. Configured listeners bind only to IPv4 or IPv6 loopback.

If any child exits unexpectedly, the runner stops its other children and exits
with status one. Press Ctrl-C in this runner's terminal to stop its application
children. This preserves integration dependency containers and their data.
The runner does not execute global `killall` or stop unrelated processes.

For runtime verification, inspect the port-manager output and each service's
logs. Confirm all eleven service child processes remain alive, including the
Kafka-only `sync` process, and all thirteen active listeners belong to this
runner. Port `36420` should remain unbound with the current source. Confirm no
unregistered listener was created and the services have no dependency errors.
A listening TCP socket only demonstrates backend readiness;
complete an actual client login followed by send/receive and upload/download
before claiming those flows work. The IPv6 listener is included in generated
runtime configuration and takes effect the next time this runner starts; an
already-running gateway keeps its loaded configuration until then.

## Local verification codes

The generated BFF configuration selects `Code.Name: "localfile"`. Requesting a
login code creates one JSON file per code hash under the absolute private
directory `server/integration/.runtime/outbox`. Directory permissions are
`0700`; code files are `0600`. The code expires after three minutes and a
successful verification consumes its file.

Read a code only in your local terminal. The following asks for the phone
number interactively, so it is not placed in shell history. Run from the
monorepo root; it prints only matching, unexpired codes and their expiry:

```bash
python3 - <<'PY'
import json
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path

phone = getpass("Phone number exactly as submitted: ")
outbox = Path("server/integration/.runtime/outbox")
now = datetime.now(timezone.utc)
for path in sorted(outbox.glob("*.json"), key=lambda item: item.stat().st_mtime):
    message = json.loads(path.read_text())
    expiry = datetime.fromisoformat(message["expires_at"].replace("Z", "+00:00"))
    if message["phone_number"] == phone and expiry > now:
        print(message["phone_code"], message["expires_at"])
PY
```

The outbox contains phone numbers and active verification codes. Do not paste
its contents into issue reports, screenshots, build logs, or commits. Runtime
configuration contains the integration database and S3 credentials; it is also
ignored by Git. Only the explicit local runtime selects this code provider.

Successful login removes its code file. An expired code is also removed when
verification is attempted. To manually clear only expired leftovers, stop this
runner first, then review and remove expired entries under this exact outbox:

```bash
python3 - <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path

outbox = Path("server/integration/.runtime/outbox")
now = datetime.now(timezone.utc)
expired = []
for path in outbox.glob("*.json"):
    message = json.loads(path.read_text())
    expiry = datetime.fromisoformat(message["expires_at"].replace("Z", "+00:00"))
    if expiry <= now:
        expired.append(path)
print(f"Expired files available to remove: {len(expired)}")
if expired and input("Type remove-expired to delete these expired entries: ") == "remove-expired":
    for path in expired:
        path.unlink()
PY
```

The cleanup command leaves unexpired codes and dependency data intact. Keep
the port registrations after stopping services.
