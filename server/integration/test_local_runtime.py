import hashlib
import json
import os
import shutil
import signal
import subprocess
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


def _der_value(data, offset, tag):
    if data[offset] != tag:
        raise AssertionError(f"unexpected DER tag: {data[offset]}")
    offset += 1
    first_length = data[offset]
    offset += 1
    if first_length & 0x80:
        length_size = first_length & 0x7f
        length = int.from_bytes(data[offset : offset + length_size], "big")
        offset += length_size
    else:
        length = first_length
    return data[offset : offset + length], offset + length


def _expected_mtproto_fingerprint(private_key):
    public_key = subprocess.run(
        ["openssl", "rsa", "-in", str(private_key), "-RSAPublicKey_out", "-outform", "DER"],
        check=True,
        capture_output=True,
    ).stdout
    sequence, _ = _der_value(public_key, 0, 0x30)
    modulus, offset = _der_value(sequence, 0, 0x02)
    exponent, _ = _der_value(sequence, offset, 0x02)
    modulus = modulus.lstrip(b"\0")

    def tl_bytes(value):
        if len(value) < 254:
            encoded = bytes([len(value)]) + value
        else:
            encoded = b"\xfe" + len(value).to_bytes(3, "little") + value
        return encoded + b"\0" * (-len(encoded) % 4)

    digest = hashlib.sha1(tl_bytes(modulus) + tl_bytes(exponent)).digest()
    return str(int.from_bytes(digest[-8:], "little"))


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
        runtime_key = self.runtime / "server_pkcs1.key"
        self.assertTrue(runtime_key.is_file())
        self.assertEqual(runtime_key.stat().st_mode & 0o777, 0o600)
        key_check = subprocess.run(
            ["openssl", "rsa", "-in", str(runtime_key), "-check", "-noout"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(key_check.returncode, 0, key_check.stderr)
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

    def test_gateway_fingerprints_match_generated_runtime_key(self):
        prepare_local.prepare_runtime(self.server, self.runtime, self.env_path)

        expected = _expected_mtproto_fingerprint(self.runtime / "server_pkcs1.key")
        gnetway = (self.runtime / "etc/gnetway.yaml").read_text(encoding="utf-8")
        configured = [
            line.split(":", 1)[1].strip().strip('"')
            for line in gnetway.splitlines()
            if "KeyFingerprint:" in line
        ]

        self.assertEqual(configured, [expected, expected])

    def test_prepare_runtime_reuses_existing_runtime_key(self):
        prepare_local.prepare_runtime(self.server, self.runtime, self.env_path)
        runtime_key = self.runtime / "server_pkcs1.key"
        first_key = runtime_key.read_bytes()
        first_fingerprint = _expected_mtproto_fingerprint(runtime_key)

        prepare_local.prepare_runtime(self.server, self.runtime, self.env_path)

        gateway = (self.runtime / "etc/gnetway.yaml").read_text(encoding="utf-8")
        configured = [
            line.split(":", 1)[1].strip().strip('"')
            for line in gateway.splitlines()
            if "KeyFingerprint:" in line
        ]
        self.assertEqual(runtime_key.read_bytes(), first_key)
        self.assertEqual(configured, [first_fingerprint, first_fingerprint])

    def test_prepare_runtime_rejects_invalid_existing_runtime_key(self):
        prepare_local.prepare_runtime(self.server, self.runtime, self.env_path)
        runtime_key = self.runtime / "server_pkcs1.key"
        invalid_key = b"not a private key\n"
        runtime_key.write_bytes(invalid_key)

        with self.assertRaisesRegex(RuntimeError, "existing local runtime RSA key is invalid"):
            prepare_local.prepare_runtime(self.server, self.runtime, self.env_path)

        self.assertEqual(runtime_key.read_bytes(), invalid_key)

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

    def test_registered_runtime_ports_override_default_endpoints(self):
        self.env_path.write_text(
            self.env_path.read_text(encoding="utf-8")
            + "LOCAL_INTEGRATION_MYSQL_PORT=23316\n"
            + "LOCAL_INTEGRATION_REDIS_PORT=26389\n"
            + "LOCAL_INTEGRATION_ETCD_PORT=22389\n"
            + "LOCAL_INTEGRATION_KAFKA_PORT=29012\n"
            + "LOCAL_INTEGRATION_MINIO_PORT=29010\n"
            + "LOCAL_INTEGRATION_MINIO_CONSOLE_PORT=29011\n"
            + "LOCAL_RUNTIME_BFF_GRPC_PORT=36010\n"
            + "LOCAL_RUNTIME_BIZ_GRPC_PORT=36020\n"
            + "LOCAL_RUNTIME_MSG_GRPC_PORT=36030\n"
            + "LOCAL_RUNTIME_SYNC_GRPC_PORT=36420\n"
            + "LOCAL_RUNTIME_AUTHSESSION_GRPC_PORT=36450\n"
            + "LOCAL_RUNTIME_MEDIA_GRPC_PORT=36650\n"
            + "LOCAL_RUNTIME_IDGEN_GRPC_PORT=36660\n"
            + "LOCAL_RUNTIME_STATUS_GRPC_PORT=36670\n"
            + "LOCAL_RUNTIME_DFS_GRPC_PORT=36640\n"
            + "LOCAL_RUNTIME_SESSION_GRPC_PORT=36120\n"
            + "LOCAL_RUNTIME_GNETWAY_GRPC_PORT=36110\n"
            + "LOCAL_RUNTIME_GNET_TCP_PORT=35222\n"
            + "LOCAL_RUNTIME_GNET_WEBSOCKET_PORT=35443\n"
            + "LOCAL_RUNTIME_DFS_HTTP_PORT=37701\n",
            encoding="utf-8",
        )

        prepare_local.prepare_runtime(self.server, self.runtime, self.env_path)

        bff = (self.runtime / "etc/bff.yaml").read_text(encoding="utf-8")
        self.assertIn("ListenOn: 127.0.0.1:36010", bff)
        self.assertIn("127.0.0.1:22389", bff)
        self.assertIn("127.0.0.1:26389", bff)
        self.assertIn("127.0.0.1:29012", bff)

        dfs = (self.runtime / "etc/dfs.yaml").read_text(encoding="utf-8")
        self.assertIn("ListenOn: 127.0.0.1:36640", dfs)
        self.assertIn("Port: 37701", dfs)
        self.assertIn("Endpoint: 127.0.0.1:29010", dfs)

        gnetway = (self.runtime / "etc/gnetway.yaml").read_text(encoding="utf-8")
        self.assertIn("ListenOn: 127.0.0.1:36110", gnetway)
        self.assertIn("127.0.0.1:35222", gnetway)
        self.assertIn("[::1]:35222", gnetway)
        self.assertIn("127.0.0.1:35443", gnetway)

        config = json.loads((self.runtime / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["data2"]["dc_options"][0]["port"], 35222)

    def test_duplicate_runtime_ports_fail_before_writing_private_runtime(self):
        self.env_path.write_text(
            self.env_path.read_text(encoding="utf-8")
            + "LOCAL_RUNTIME_BFF_GRPC_PORT=36010\n"
            + "LOCAL_RUNTIME_BIZ_GRPC_PORT=36010\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(RuntimeError, "local runtime ports must be unique"):
            prepare_local.prepare_runtime(self.server, self.runtime, self.env_path)

        self.assertFalse(self.runtime.exists())


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
