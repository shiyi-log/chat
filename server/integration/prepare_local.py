import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path


SERVICE_PORTS = {
    "idgen": 30660,
    "status": 30670,
    "dfs": 30640,
    "media": 30650,
    "authsession": 30450,
    "biz": 30020,
    "msg": 30030,
    "sync": 30420,
    "bff": 30010,
    "session": 30120,
    "gnetway": 30110,
}
TCP_PORT = 25222
WEBSOCKET_PORT = 25443
DFS_HTTP_PORT = 31701

_MYSQL_PASSWORD_KEY = "LOCAL_INTEGRATION_MYSQL_PASSWORD"
_MINIO_PASSWORD_KEY = "LOCAL_INTEGRATION_MINIO_ROOT_PASSWORD"
_REQUIRED_ENV = (
    "LOCAL_INTEGRATION_MYSQL_ROOT_PASSWORD",
    _MYSQL_PASSWORD_KEY,
    _MINIO_PASSWORD_KEY,
)


def _read_env_file(env_path):
    values = {}
    try:
        lines = Path(env_path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError("required integration credentials are unavailable") from exc

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            raise RuntimeError("required integration credentials file is malformed")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value

    if any(not values.get(key) for key in _REQUIRED_ENV):
        raise RuntimeError("required integration credentials are missing")
    return values


def _ensure_private_dir(path):
    path = Path(path)
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not path.is_dir() or path.is_symlink():
            raise RuntimeError("local runtime path must be a real directory")
    else:
        path.mkdir(parents=True, mode=0o700)
    path.chmod(0o700)
    return path


def _write_private_file(path, contents):
    path = Path(path)
    path.write_text(contents, encoding="utf-8")
    path.chmod(0o600)


def _quoted(value):
    return json.dumps(value, ensure_ascii=True)


def _replace_once(text, old, new, description):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"unexpected {description} in source configuration")
    return text.replace(old, new, 1)


def _render_service_config(name, source_path, runtime_root, credentials):
    text = source_path.read_text(encoding="utf-8")
    old_port = {
        "bff": 20010,
        "biz": 20020,
        "msg": 20030,
        "sync": 20420,
        "authsession": 20450,
        "media": 20650,
        "idgen": 20660,
        "status": 20670,
        "dfs": 20640,
        "session": 20120,
        "gnetway": 20110,
    }[name]
    text = _replace_once(
        text,
        f"ListenOn: 127.0.0.1:{old_port}\n",
        f"ListenOn: 127.0.0.1:{SERVICE_PORTS[name]}\n",
        f"{name} gRPC listener",
    )
    text, name_count = re.subn(r"(?m)^(Name: [^\n]+)$", r"\1\nMode: pro", text, count=1)
    if name_count != 1:
        raise RuntimeError(f"unexpected {name} service name in source configuration")
    text = _replace_once(
        text,
        f"ListenOn: 127.0.0.1:{SERVICE_PORTS[name]}\n",
        f"ListenOn: 127.0.0.1:{SERVICE_PORTS[name]}\nDevServer:\n  Enabled: false\n",
        f"{name} dev server setting",
    )

    for old, new in (
        ("127.0.0.1:2379", "127.0.0.1:22379"),
        ("127.0.0.1:6379", "127.0.0.1:26379"),
        ("localhost:6379", "127.0.0.1:26379"),
        ("127.0.0.1:9092", "127.0.0.1:29092"),
    ):
        text = text.replace(old, new)

    if name == "bff":
        text = _replace_once(text, "  Level: debug\n", "  Level: info\n", "BFF local log level")
        text = _replace_once(text, '  Name: "none"\n', '  Name: "localfile"\n', "BFF code provider")
        outbox = os.path.abspath(runtime_root / "outbox")
        text = _replace_once(
            text,
            '  RegionId: ""\n',
            f'  RegionId: ""\n  LocalOutboxDir: {_quoted(outbox)}\n',
            "BFF local outbox",
        )

    dsn = f"teamgram:{credentials[_MYSQL_PASSWORD_KEY]}@tcp(127.0.0.1:23306)/teamgram?charset=utf8mb4&parseTime=true"
    text, dsn_count = re.subn(
        r"(?m)^(\s*DSN:) root:@tcp\(127\.0\.0\.1:3306\)/teamgram\?charset=utf8mb4&parseTime=true$",
        lambda match: f"{match.group(1)} {_quoted(dsn)}",
        text,
    )
    if dsn_count not in (0, 1):
        raise RuntimeError(f"unexpected MySQL DSN count in {name} source configuration")

    if name == "dfs":
        text = _replace_once(text, "  Host: 0.0.0.0\n  Port: 11701\n", f"  Host: 127.0.0.1\n  Port: {DFS_HTTP_PORT}\n", "DFS HTTP listener")
        text = _replace_once(
            text,
            f"  Port: {DFS_HTTP_PORT}\n  Timeout: 0\n",
            f"  Port: {DFS_HTTP_PORT}\n  DevServer:\n    Enabled: false\n  Timeout: 0\n",
            "DFS HTTP dev server setting",
        )
        text = _replace_once(text, "  Endpoint: localhost:9000\n", "  Endpoint: 127.0.0.1:29000\n", "MinIO endpoint")
        text = _replace_once(text, "  AccessKeyID: minio\n", "  AccessKeyID: integration-minio\n", "MinIO username")
        text = _replace_once(
            text,
            "  SecretAccessKey: miniostorage\n",
            f"  SecretAccessKey: {_quoted(credentials[_MINIO_PASSWORD_KEY])}\n",
            "MinIO credential",
        )

    if name == "gnetway":
        key_path = os.path.abspath(runtime_root / "server_pkcs1.key")
        text = text.replace('"./server_pkcs1.key"', _quoted(key_path))
        if text.count(key_path) != 2:
            raise RuntimeError("unexpected gateway RSA key references in source configuration")
        text = _replace_once(text, "0.0.0.0:10443", f"127.0.0.1:{TCP_PORT}", "gateway TCP listener")
        text = _replace_once(text, "        - 0.0.0.0:5222\n", "        - \"[::1]:25222\"\n", "gateway IPv6 loopback TCP listener")
        text = _replace_once(text, "0.0.0.0:11443", f"127.0.0.1:{WEBSOCKET_PORT}", "gateway WebSocket listener")

    text, log_path_count = re.subn(
        r"(?m)^(  Path: )\.\./logs/[^\n]+$",
        lambda match: f"{match.group(1)}{_quoted(os.path.abspath(runtime_root / 'logs' / name))}",
        text,
        count=1,
    )
    if log_path_count != 1:
        raise RuntimeError(f"unexpected {name} log path in source configuration")
    return text


def _render_client_config(source_path):
    config = json.loads(source_path.read_text(encoding="utf-8"))
    data = config.get("data2")
    if not isinstance(data, dict) or not isinstance(data.get("dc_options"), list):
        raise RuntimeError("client config has an unexpected dc_options structure")
    data["dc_options"] = [
        {
            "predicate_name": "dcOption",
            "id": 1,
            "ip_address": "127.0.0.1",
            "port": TCP_PORT,
        },
    ]
    return json.dumps(config, indent=2, ensure_ascii=True) + "\n"


def prepare_runtime(server_root, runtime_root, env_path):
    server_root = Path(server_root).resolve()
    runtime_root = Path(os.path.abspath(runtime_root))
    credentials = _read_env_file(env_path)
    source_dir = server_root / "teamgramd" / "etc"
    key_source = server_root / "teamgramd" / "bin" / "server_pkcs1.key"
    client_config_source = server_root / "teamgramd" / "bin" / "config.json"

    source_configs = {name: source_dir / f"{name}.yaml" for name in SERVICE_PORTS}
    missing = [path for path in [*source_configs.values(), key_source, client_config_source] if not path.is_file()]
    if missing:
        raise RuntimeError("local runtime source files are incomplete")

    rendered = {
        name: _render_service_config(name, source, runtime_root, credentials)
        for name, source in source_configs.items()
    }
    client_config = _render_client_config(client_config_source)

    _ensure_private_dir(runtime_root)
    etc_dir = _ensure_private_dir(runtime_root / "etc")
    _ensure_private_dir(runtime_root / "logs")
    outbox_dir = _ensure_private_dir(runtime_root / "outbox")
    for name, contents in rendered.items():
        _write_private_file(etc_dir / f"{name}.yaml", contents)
    _write_private_file(runtime_root / "config.json", client_config)
    shutil.copyfile(key_source, runtime_root / "server_pkcs1.key")
    (runtime_root / "server_pkcs1.key").chmod(0o600)
    outbox_dir.chmod(0o700)
    return [etc_dir / f"{name}.yaml" for name in SERVICE_PORTS]


class ManagedServices:
    def __init__(self, runtime_root):
        self.runtime_root = Path(runtime_root)
        self.children = []

    def start(self, name, command, cwd=None):
        if not name.isalnum():
            raise ValueError("service name must be alphanumeric")
        logs = _ensure_private_dir(self.runtime_root / "logs")
        log_path = logs / f"{name}.stdout.log"
        descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.chmod(log_path, 0o600)
        with os.fdopen(descriptor, "ab") as output:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                close_fds=True,
            )
        self.children.append((name, process))
        return process

    def stop(self, timeout=10):
        children = [process for _, process in reversed(self.children)]
        for process in children:
            if process.poll() is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass

        deadline = time.monotonic() + timeout
        for process in children:
            if process.poll() is None:
                try:
                    process.wait(timeout=max(0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    process.wait()
