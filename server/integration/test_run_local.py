import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prepare_local
import run_local


SERVICE_NAMES = (
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


class BuildCommandsTests(unittest.TestCase):
    def test_commands_use_each_runtime_config_and_binary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            server = root / "server"
            runtime = root / "runtime"
            binaries = server / "teamgramd" / "bin"
            configs = runtime / "etc"
            binaries.mkdir(parents=True)
            configs.mkdir(parents=True)
            for name in SERVICE_NAMES:
                binary = binaries / name
                binary.touch()
                binary.chmod(0o700)
                (configs / f"{name}.yaml").touch()

            commands = run_local.build_commands(server, runtime)

        self.assertEqual([name for name, _ in commands], list(SERVICE_NAMES))
        for name, command in commands:
            self.assertEqual(command[0], str((binaries / name).resolve()))
            self.assertEqual(command[1], f"-f={(configs / f'{name}.yaml').resolve()}")

    def test_missing_binary_is_reported_before_any_service_starts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            server = root / "server"
            runtime = root / "runtime"
            (server / "teamgramd" / "bin").mkdir(parents=True)
            (runtime / "etc").mkdir(parents=True)

            with self.assertRaisesRegex(RuntimeError, "idgen"):
                run_local.build_commands(server, runtime)


class RunServicesTests(unittest.TestCase):
    def test_child_failure_stops_other_services_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir)
            manager = prepare_local.ManagedServices(runtime)
            commands = [
                ("worker", [sys.executable, "-c", "import time; time.sleep(30)"]),
                ("failure", [sys.executable, "-c", "raise SystemExit(9)"]),
            ]

            result = run_local.run_services(
                commands,
                manager,
                runtime,
                threading.Event(),
                poll_interval=0.01,
            )

            self.assertEqual(result, 1)
            self.assertTrue(all(process.poll() is not None for _, process in manager.children))

    def test_stop_event_terminates_children_and_returns_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir)
            manager = prepare_local.ManagedServices(runtime)
            stop_event = threading.Event()
            stop_event.set()

            result = run_local.run_services(
                [("worker", [sys.executable, "-c", "import time; time.sleep(30)"])],
                manager,
                runtime,
                stop_event,
                poll_interval=0.01,
            )

            self.assertEqual(result, 0)
            self.assertIsNotNone(manager.children[0][1].poll())


if __name__ == "__main__":
    unittest.main()
