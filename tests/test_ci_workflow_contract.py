import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"


class CiWorkflowContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not WORKFLOW.is_file():
            raise AssertionError("Missing root GitHub Actions workflow: .github/workflows/ci.yml")
        parsed = subprocess.run(
            [
                "ruby",
                "-ryaml",
                "-rjson",
                "-e",
                "puts JSON.generate(YAML.safe_load(File.read(ARGV.fetch(0)), aliases: true))",
                str(WORKFLOW),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        cls.workflow = json.loads(parsed.stdout)

    def test_pull_requests_run_read_only_repository_checks(self):
        triggers = self.workflow.get("on", self.workflow.get("true"))
        if triggers is None:
            triggers = self.workflow.get(True)

        self.assertIn("pull_request", triggers)
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertNotIn("pull_request_target", triggers)

        jobs = self.workflow["jobs"]
        self.assertTrue({"repository", "server", "android-compile"}.issubset(jobs))

    def test_repository_job_runs_each_component_validator(self):
        steps = self.workflow["jobs"]["repository"]["steps"]
        commands = "\n".join(step.get("run", "") for step in steps)

        self.assertIn("python -m unittest discover -s tests", commands)
        self.assertIn("scripts/verify_private_chat_android_config.py", commands)
        self.assertIn("scripts/tests/test_private_chat_api_config.py", commands)
        self.assertIn("scripts/tests/test_chat_branding_localization.py", commands)
        self.assertIn("scripts/tests/test_chat_app_branding.py", commands)
        self.assertIn("scripts/test_chat_desktop_branding.py", commands)
        self.assertIn("scripts/verify_private_chat_ios_config.py", commands)
        self.assertIn("scripts/verify_private_chat_desktop_config.py", commands)

    def test_server_job_runs_only_the_scoped_offline_unit_packages(self):
        steps = self.workflow["jobs"]["server"]["steps"]
        commands = "\n".join(step.get("run", "") for step in steps)

        self.assertIn("go test ./pkg/hashx", commands)
        self.assertIn("./pkg/phonenumber", commands)
        self.assertIn("./pkg/mention", commands)
        self.assertIn("./pkg/code/none", commands)
        self.assertIn("./pkg/code/localfile", commands)
        self.assertIn("./app/interface/session/internal/sess", commands)
        self.assertNotIn("go test ./...", commands)

    def test_android_compile_avoids_packaging_and_signing_tasks(self):
        android = self.workflow["jobs"]["android-compile"]
        commands = "\n".join(step.get("run", "") for step in android["steps"])

        self.assertIn("compileAfatDebugJavaWithJavac", commands)
        self.assertNotIn("assembleAfat", commands)
        self.assertNotIn("signingConfig", commands)
        self.assertEqual(android["permissions"], {"contents": "read"})


if __name__ == "__main__":
    unittest.main()
