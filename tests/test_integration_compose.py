import json
import re
import tempfile
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "server" / "docker-compose-integration.yaml"
INTEGRATION_README = ROOT / "server" / "integration" / "README.md"
PROJECT_NAME = "chat-monorepo-public-integration"
EXPECTED_PORTS = {
    ("mysql", 3306): 23306,
    ("redis", 6379): 26379,
    ("etcd", 2379): 22379,
    ("kafka", 19092): 29092,
    ("minio", 9000): 29000,
    ("minio", 9001): 29001,
}


class IntegrationComposeTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(COMPOSE_FILE.is_file(), "isolated integration Compose file is missing")
        self.env_file = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8")
        self.addCleanup(self.env_file.close)
        self.env_file.write(
            "LOCAL_INTEGRATION_MYSQL_ROOT_PASSWORD=test-root-password\n"
            "LOCAL_INTEGRATION_MYSQL_PASSWORD=test-mysql-password\n"
            "LOCAL_INTEGRATION_MINIO_ROOT_PASSWORD=test-minio-password\n"
        )
        self.env_file.flush()
        result = subprocess.run(
            [
                "docker", "compose", "--env-file", self.env_file.name,
                "-f", str(COMPOSE_FILE), "config", "--format", "json",
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.config = json.loads(result.stdout)

    def test_core_services_have_distinct_loopback_only_ports(self):
        services = self.config["services"]
        self.assertTrue(set(name for name, _ in EXPECTED_PORTS) <= services.keys())
        published_ports = []
        for (service_name, target_port), host_port in EXPECTED_PORTS.items():
            with self.subTest(service=service_name, target=target_port):
                matches = [
                    port for port in services[service_name].get("ports", [])
                    if int(port["target"]) == target_port
                ]
                self.assertEqual(1, len(matches))
                self.assertEqual("127.0.0.1", matches[0]["host_ip"])
                self.assertEqual(host_port, int(matches[0]["published"]))
                published_ports.append(int(matches[0]["published"]))
        self.assertEqual(len(published_ports), len(set(published_ports)))
        self.assertEqual(
            len(EXPECTED_PORTS),
            sum(len(service.get("ports", [])) for service in services.values()),
        )

    def test_registered_host_ports_are_configurable_and_advertised(self):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as env_file:
            env_file.write(
                "LOCAL_INTEGRATION_MYSQL_ROOT_PASSWORD=test-root-password\n"
                "LOCAL_INTEGRATION_MYSQL_PASSWORD=test-mysql-password\n"
                "LOCAL_INTEGRATION_MINIO_ROOT_PASSWORD=test-minio-password\n"
                "LOCAL_INTEGRATION_MYSQL_PORT=23316\n"
                "LOCAL_INTEGRATION_REDIS_PORT=26389\n"
                "LOCAL_INTEGRATION_ETCD_PORT=22389\n"
                "LOCAL_INTEGRATION_KAFKA_PORT=29012\n"
                "LOCAL_INTEGRATION_MINIO_PORT=29010\n"
                "LOCAL_INTEGRATION_MINIO_CONSOLE_PORT=29011\n"
            )
            env_file.flush()
            result = subprocess.run(
                [
                    "docker", "compose", "--env-file", env_file.name,
                    "-f", str(COMPOSE_FILE), "config", "--format", "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

        config = json.loads(result.stdout)
        services = config["services"]
        expected_ports = {
            ("mysql", 3306): 23316,
            ("redis", 6379): 26389,
            ("etcd", 2379): 22389,
            ("kafka", 19092): 29012,
            ("minio", 9000): 29010,
            ("minio", 9001): 29011,
        }
        for (service_name, target_port), host_port in expected_ports.items():
            with self.subTest(service=service_name, target=target_port):
                matches = [
                    port for port in services[service_name].get("ports", [])
                    if int(port["target"]) == target_port
                ]
                self.assertEqual(1, len(matches))
                self.assertEqual(host_port, int(matches[0]["published"]))

        etcd = services["etcd"]["environment"]
        kafka = services["kafka"]["environment"]
        self.assertEqual("http://127.0.0.1:22389", etcd["ETCD_ADVERTISE_CLIENT_URLS"])
        self.assertIn("HOST://127.0.0.1:29012", kafka["KAFKA_ADVERTISED_LISTENERS"])

    def test_stateful_services_use_only_project_scoped_named_data_volumes(self):
        services = self.config["services"]
        data_targets = {
            "mysql": "/var/lib/mysql",
            "redis": "/data",
            "etcd": "/etcd-data",
            "kafka": "/var/lib/kafka/data",
            "minio": "/data",
        }
        for service_name in ("mysql", "redis", "etcd", "kafka", "minio"):
            with self.subTest(service=service_name):
                mounts = services[service_name].get("volumes", [])
                data_mounts = [
                    mount for mount in mounts
                    if mount["target"] == data_targets[service_name]
                ]
                self.assertTrue(data_mounts)
                for mount in data_mounts:
                    self.assertEqual("volume", mount["type"])
                    volume = self.config["volumes"][mount["source"]]
                    self.assertTrue(volume["name"].startswith(f"{PROJECT_NAME}_"))

    def test_compose_identity_is_isolated_from_existing_server_stack(self):
        self.assertEqual(PROJECT_NAME, self.config["name"])
        for service in self.config["services"].values():
            self.assertNotIn("container_name", service)
            self.assertNotIn("network_mode", service)
            self.assertNotIn("external_links", service)
            for mount in service.get("volumes", []):
                if mount["type"] == "bind":
                    self.assertTrue(mount.get("read_only"), "host mounts must be read-only")
                    Path(mount["source"]).resolve().relative_to(ROOT)
                    self.assertNotIn("data", Path(mount["source"]).relative_to(ROOT).parts)
        for volume in self.config["volumes"].values():
            self.assertFalse(volume.get("external", False))
            self.assertTrue(volume["name"].startswith(f"{PROJECT_NAME}_"))
        for network in self.config["networks"].values():
            self.assertFalse(network.get("external", False))
            self.assertFalse(network.get("ipam", {}).get("config"))

    def test_documented_compose_commands_use_the_declared_project_name(self):
        readme = INTEGRATION_README.read_text(encoding="utf-8")
        project_names = re.findall(
            r"docker compose --project-name (\S+)", readme
        )

        self.assertTrue(project_names)
        self.assertEqual({PROJECT_NAME}, set(project_names))

    def test_kafka_advertises_reachable_internal_and_host_listeners(self):
        environment = self.config["services"]["kafka"]["environment"]
        self.assertIn("INTERNAL://kafka:9092", environment["KAFKA_ADVERTISED_LISTENERS"])
        self.assertIn("HOST://127.0.0.1:29092", environment["KAFKA_ADVERTISED_LISTENERS"])
        self.assertIn("CONTROLLER://kafka:9093", environment["KAFKA_ADVERTISED_LISTENERS"])

    def test_etcd_advertises_host_reachable_client_endpoint(self):
        environment = self.config["services"]["etcd"]["environment"]
        self.assertEqual("http://127.0.0.1:22379", environment["ETCD_ADVERTISE_CLIENT_URLS"])

    def test_s3_service_uses_pinned_rustfs_and_waits_for_readiness_before_bucket_setup(self):
        services = self.config["services"]
        self.assertRegex(services["minio"]["image"], r"^rustfs/rustfs@sha256:[0-9a-f]{64}$")
        self.assertRegex(services["minio-init"]["image"], r"^rustfs/rc@sha256:[0-9a-f]{64}$")
        self.assertEqual("service_healthy", services["minio-init"]["depends_on"]["minio"]["condition"])
        healthcheck = services["minio"]["healthcheck"]["test"]
        self.assertIn("http://127.0.0.1:9000/health", healthcheck)


if __name__ == "__main__":
    unittest.main()
