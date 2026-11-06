import json
import os
import shutil
import signal
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prepare_local


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_PORTS = {
    "bff": 30010,
    "biz": 30020,
    "msg": 30030,
    "sync": 30420,
    "authsession": 30450,
    "media": 30650,
    "idgen": 30660,
    "status": 30670,
    "dfs": 30640,
    "session": 30120,
    "gnetway": 30110,
}


class PrepareRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.server = self.root / "server"
        self.runtime = self.server / "integration" / ".runtime"
        self.etc = self.server / "teamgramd" / "etc"
        self.bin = self.server / "teamgramd" / "bin"
        self.etc.mkdir(parents=True)
        self.bin.mkdir(parents=True)
        (self.server / "integration").mkdir(exist_ok=True)
        for name in SERVICE_PORTS:
            shutil.copy(REPO_ROOT / "server/teamgramd/etc" / f"{name}.yaml", self.etc)
        shutil.copy(REPO_ROOT / "server/teamgramd/bin/config.json", self.bin)
        shutil.copy(REPO_ROOT / "server/teamgramd/bin/server_pkcs1.key", self.bin)
        self.env_path = self.server / "integration" / ".env"
        self.env_path.write_text(
            "LOCAL_INTEGRATION_MYSQL_ROOT_PASSWORD=root-secret\n"
            "LOCAL_INTEGRATION_MYSQL_PASSWORD=app-secret\n"
            "LOCAL_INTEGRATION_MINIO_ROOT_PASSWORD=minio-secret\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_prepare_builds_private_runtime_configs_without_changing_defaults(self):
        source_before = {path.name: path.read_bytes() for path in self.etc.glob("*.yaml")}

        config_paths = prepare_local.prepare_runtime(self.server, self.runtime, self.env_path)

        self.assertEqual(set(path.name for path in config_paths), {f"{name}.yaml" for name in SERVICE_PORTS})
        for name, port in SERVICE_PORTS.items():
            text = (self.runtime / "etc" / f"{name}.yaml").read_text(encoding="utf-8")
            self.assertIn(f"ListenOn: 127.0.0.1:{port}\n", text)
            self.assertIn("DevServer:\n  Enabled: false\n", text)
            self.assertNotIn("127.0.0.1:2379", text)
            self.assertNotIn("127.0.0.1:6379", text)
            self.assertNotIn("localhost:6379", text)
            self.assertNotIn("127.0.0.1:9092", text)
            self.assertNotIn("127.0.0.1:3306", text)
            self.assertNotIn("0.0.0.0:", "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#")))
            self.assertEqual((self.runtime / "etc" / f"{name}.yaml").stat().st_mode & 0o777, 0o600)

        bff = (self.runtime / "etc/bff.yaml").read_text(encoding="utf-8")
        self.assertIn('Name: "localfile"', bff)
        self.assertIn(f'LocalOutboxDir: "{self.runtime / "outbox"}"', bff)
        self.assertIn("  Level: info\n", bff)
        self.assertIn("127.0.0.1:29092", bff)

        dfs = (self.runtime / "etc/dfs.yaml").read_text(encoding="utf-8")
        self.assertIn("Host: 127.0.0.1\n  Port: 31701", dfs)
        self.assertIn("Endpoint: 127.0.0.1:29000", dfs)
        self.assertIn("AccessKeyID: integration-minio", dfs)

        gnetway = (self.runtime / "etc/gnetway.yaml").read_text(encoding="utf-8")
        self.assertIn("127.0.0.1:25222", gnetway)
        self.assertIn("[::1]:25222", gnetway)
        self.assertIn("127.0.0.1:25443", gnetway)
        self.assertNotIn("10443", gnetway)
        self.assertNotIn("0.0.0.0:5222", gnetway)
        self.assertIn(str(self.runtime / "server_pkcs1.key"), gnetway)

        config = json.loads((self.runtime / "config.json").read_text(encoding="utf-8"))
        options = config["data2"]["dc_options"]
        self.assertEqual([entry["port"] for entry in options], [25222])
        self.assertEqual({entry["ip_address"] for entry in options}, {"127.0.0.1"})
        self.assertTrue(all(entry["predicate_name"] == "dcOption" for entry in options))
        self.assertEqual(source_before, {path.name: path.read_bytes() for path in self.etc.glob("*.yaml")})
        self.assertEqual(self.runtime.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.runtime / "outbox").stat().st_mode & 0o777, 0o700)

    def test_missing_credentials_fail_without_echoing_secret_values(self):
        secret = "sensitive-value-must-not-appear"
        self.env_path.write_text(
            f"LOCAL_INTEGRATION_MYSQL_ROOT_PASSWORD={secret}\n"
            "LOCAL_INTEGRATION_MYSQL_PASSWORD=\n"
            "LOCAL_INTEGRATION_MINIO_ROOT_PASSWORD=minio-secret\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(RuntimeError, "required integration credentials") as raised:
            prepare_local.prepare_runtime(self.server, self.runtime, self.env_path)

        self.assertNotIn(secret, str(raised.exception))
        self.assertFalse(self.runtime.exists())

    def test_short_nonempty_credentials_are_accepted(self):
        config_paths = prepare_local.prepare_runtime(self.server, self.runtime, self.env_path)

        self.assertEqual(len(config_paths), len(SERVICE_PORTS))

    def test_dfs_mini_http_disables_its_embedded_dev_server(self):
        prepare_local.prepare_runtime(self.server, self.runtime, self.env_path)

        dfs = (self.runtime / "etc/dfs.yaml").read_text(encoding="utf-8")
        mini_http = dfs.split("MiniHttp:\n", 1)[1].split("Cache:\n", 1)[0]

        self.assertIn("  DevServer:\n    Enabled: false\n", mini_http)


class ManagedServicesTests(unittest.TestCase):
    def test_stop_terminates_only_the_child_owned_by_this_manager(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir)
            manager = prepare_local.ManagedServices(runtime)
            external = __import__("subprocess").Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            try:
                owned = manager.start("owned", [sys.executable, "-c", "import time; time.sleep(30)"])
                manager.stop()
                self.assertIsNotNone(owned.poll())
                self.assertIsNone(external.poll())
            finally:
                external.send_signal(signal.SIGTERM)
                external.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
