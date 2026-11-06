import argparse
import signal
import sys
import threading
from pathlib import Path

import prepare_local


SERVICE_ORDER = (
    "idgen",
    "status",
    "dfs",
    "media",
    "authsession",
    "biz",
    "msg",
    "sync",
    "bff",
    "session",
    "gnetway",
)


def build_commands(server_root, runtime_root):
    server_root = Path(server_root).resolve()
    runtime_root = Path(runtime_root).resolve()
    binary_dir = server_root / "teamgramd" / "bin"
    commands = []
    for name in SERVICE_ORDER:
        binary = binary_dir / name
        if not binary.is_file() or not binary.stat().st_mode & 0o111:
            raise RuntimeError(f"built executable is missing for service: {name}")
        config = runtime_root / "etc" / f"{name}.yaml"
        commands.append((name, [str(binary), f"-f={config}"]))
    return commands


def run_services(commands, manager, runtime_root, stop_event, poll_interval=0.25):
    runtime_root = Path(runtime_root).resolve()
    processes = []
    try:
        for name, command in commands:
            process = manager.start(name, command, cwd=runtime_root)
            processes.append((name, process))

        while not stop_event.wait(poll_interval):
            for name, process in processes:
                exit_code = process.poll()
                if exit_code is not None:
                    print(f"{name} exited unexpectedly with status {exit_code}", file=sys.stderr)
                    return 1
        return 0
    finally:
        manager.stop()


def main(argv=None):
    default_server_root = Path(__file__).resolve().parents[1]
    default_runtime_root = Path(__file__).resolve().parent / ".runtime"
    parser = argparse.ArgumentParser(description="Run the Private Chat Go services locally")
    parser.add_argument("--server-root", type=Path, default=default_server_root)
    parser.add_argument("--runtime-root", type=Path, default=default_runtime_root)
    parser.add_argument("--env-file", type=Path, default=Path(__file__).resolve().parent / ".env")
    args = parser.parse_args(argv)

    try:
        commands = build_commands(args.server_root, args.runtime_root)
        prepare_local.prepare_runtime(args.server_root, args.runtime_root, args.env_file)
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    manager = prepare_local.ManagedServices(args.runtime_root)
    stop_event = threading.Event()
    previous_handlers = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.signal(signum, lambda _signum, _frame: stop_event.set())

    try:
        print(f"Starting {len(commands)} local Go services; logs: {args.runtime_root / 'logs'}")
        return run_services(commands, manager, args.runtime_root, stop_event)
    except OSError as exc:
        print(f"could not start local services: {exc}", file=sys.stderr)
        manager.stop()
        return 1
    finally:
        for signum, previous_handler in previous_handlers.items():
            signal.signal(signum, previous_handler)


if __name__ == "__main__":
    raise SystemExit(main())
