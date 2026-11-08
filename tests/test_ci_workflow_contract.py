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
        self.assertIn("scripts/tests/test_android_emulator_smoke.py", commands)
        self.assertIn("scripts/tests/test_chat_app_branding.py", commands)
        self.assertIn("scripts/test_chat_desktop_branding.py", commands)
        self.assertIn("scripts/verify_private_chat_ios_config.py", commands)
        self.assertIn("scripts/verify_private_chat_desktop_config.py", commands)

    def test_ios_config_step_sets_package_import_path(self):
        steps = self.workflow["jobs"]["repository"]["steps"]
        ios_step = next(step for step in steps if step.get("name") == "Run iOS configuration checks")

        self.assertEqual("clients/ios", ios_step.get("env", {}).get("PYTHONPATH"))

    def test_server_job_runs_only_the_scoped_offline_unit_packages(self):
        steps = self.workflow["jobs"]["server"]["steps"]
        commands = "\n".join(step.get("run", "") for step in steps)

        self.assertIn("go test ./pkg/hashx", commands)
        self.assertIn("./pkg/phonenumber", commands)
        self.assertIn("./pkg/mention", commands)
        self.assertIn("./pkg/code/none", commands)
        self.assertIn("./pkg/code/localfile", commands)
        self.assertIn("./app/interface/session/internal/sess", commands)
        self.assertIn("./app/bff/authorization/internal/core", commands)
        self.assertIn("./app/interface/gnetway/internal/dao", commands)
        self.assertNotIn("go test ./...", commands)

    def test_server_job_runs_local_runtime_configuration_tests(self):
        steps = self.workflow["jobs"]["server"]["steps"]
        commands = "\n".join(step.get("run", "") for step in steps)

        self.assertIn("python -m unittest server.integration.test_local_runtime server.integration.test_run_local -v", commands)

    def test_server_preview_job_builds_and_uploads_all_service_binaries(self):
        server_build = self.workflow["jobs"]["server-build-preview"]
        commands = "\n".join(step.get("run", "") for step in server_build["steps"])
        archive = next(
            step
            for step in server_build["steps"]
            if step.get("name") == "Verify and archive server binaries"
        )
        artifact = next(
            step
            for step in server_build["steps"]
            if step.get("name") == "Upload Linux server preview"
        )

        self.assertEqual("ubuntu-24.04", server_build["runs-on"])
        build = next(step for step in server_build["steps"] if step.get("name") == "Build server services")
        self.assertEqual("server", build.get("working-directory"))
        self.assertIn("make all", commands)
        for binary in (
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
        ):
            self.assertIn(binary, commands)

        self.assertEqual("actions/upload-artifact@v7", artifact.get("uses"))
        self.assertEqual(
            "chat-server-linux-preview-${{ github.run_id }}-${{ github.run_attempt }}",
            artifact["with"]["name"],
        )
        self.assertEqual("${{ runner.temp }}/chat-server-linux-preview.tar.gz", artifact["with"]["path"])
        self.assertEqual(14, artifact["with"]["retention-days"])
        self.assertEqual("error", artifact["with"]["if-no-files-found"])
        self.assertEqual({"contents": "read"}, server_build["permissions"])
        archive_command = " ".join(archive["run"].replace("\\\n", " ").split())
        self.assertIn(
            "-C server/teamgramd/bin idgen status dfs media authsession biz msg sync bff session gnetway",
            archive_command,
        )
        self.assertNotIn("-C server/teamgramd/bin .", archive_command)

    def test_android_debug_apk_job_builds_and_uploads_only_debug_artifacts(self):
        android = self.workflow["jobs"]["android-compile"]
        commands = "\n".join(step.get("run", "") for step in android["steps"])
        artifact = next(step for step in android["steps"] if step.get("name") == "Upload Android debug APK preview")

        self.assertIn("assembleAfatDebug", commands)
        self.assertEqual("actions/upload-artifact@v7", artifact.get("uses"))
        self.assertEqual("clients/android/TMessagesProj_App/build/outputs/apk/afat/debug/app.apk", artifact["with"]["path"])
        self.assertEqual(
            "chat-android-afat-debug-${{ github.run_id }}-${{ github.run_attempt }}",
            artifact["with"]["name"],
        )
        self.assertEqual(14, artifact["with"]["retention-days"])
        self.assertNotIn("assembleAfatRelease", commands)
        self.assertNotIn("signingConfig", commands)
        self.assertEqual(android["permissions"], {"contents": "read"})

    def test_android_preview_must_pass_a_chinese_first_launch_emulator_smoke(self):
        jobs = self.workflow["jobs"]
        smoke = jobs.get("android-emulator-smoke")
        self.assertIsNotNone(smoke, "the built APK must be installed and launched on an emulator")
        self.assertEqual(["android-compile"], smoke["needs"])

        commands = "\n".join(step.get("run", "") for step in smoke["steps"])
        self.assertTrue(any(step.get("uses") == "actions/setup-java@v6" for step in smoke["steps"]))
        self.assertIn("system-images;android-35;google_apis;x86_64", commands)
        self.assertIn("smoke_android_emulator.py", commands)
        smoke_script = ROOT / "clients/android/scripts/smoke_android_emulator.py"
        script = smoke_script.read_text(encoding="utf-8")
        self.assertIn("uiautomator", script)
        self.assertIn('"pm", "clear"', script)

        download = next(step for step in smoke["steps"] if step.get("name") == "Download Android debug APK")
        self.assertEqual("actions/download-artifact@v7", download.get("uses"))
        self.assertEqual(
            "chat-android-afat-debug-${{ github.run_id }}-${{ github.run_attempt }}",
            download["with"]["name"],
        )

        candidate = jobs["candidate-package"]
        self.assertIn("android-emulator-smoke", candidate["needs"])

    def test_ios_simulator_build_uses_the_unsigned_local_configuration(self):
        ios = self.workflow["jobs"]["ios-simulator-build"]
        commands = "\n".join(step.get("run", "") for step in ios["steps"])
        artifact = next(step for step in ios["steps"] if step.get("name") == "Upload unsigned iOS simulator preview")

        self.assertEqual("xcode-27", ios["runs-on"])
        self.assertIn("generateProject", commands)
        self.assertIn("xcodebuild", commands)
        self.assertIn("-sdk iphonesimulator", commands)
        self.assertIn("CODE_SIGNING_ALLOWED=NO", commands)
        self.assertIn("build-system/template_minimal_development_configuration.json", commands)
        self.assertIn("build-system/fake-codesigning", commands)
        self.assertIn("--noOpen", commands)
        self.assertIn("test_make_project_generation.py", commands)
        self.assertIn("Chat-iOS-Simulator.zip", commands)
        self.assertEqual("actions/upload-artifact@v7", artifact.get("uses"))
        self.assertEqual(
            "chat-ios-simulator-debug-${{ github.run_id }}-${{ github.run_attempt }}",
            artifact["with"]["name"],
        )
        self.assertEqual(14, artifact["with"]["retention-days"])
        self.assertNotIn("TELEGRAM_CODESIGNING_GIT_PASSWORD", commands)
        self.assertNotIn("--gitCodesigningRepository", commands)

    def test_desktop_packaging_metadata_runs_on_each_native_desktop_host(self):
        desktop = self.workflow["jobs"]["desktop-packaging-metadata"]
        platforms = desktop["strategy"]["matrix"]["os"]
        commands = "\n".join(step.get("run", "") for step in desktop["steps"])

        self.assertEqual(["ubuntu-24.04", "windows-2025", "macos-26"], platforms)
        self.assertIn("verify_private_chat_desktop_config.py", commands)
        self.assertIn("test_chat_desktop_branding.py", commands)


if __name__ == "__main__":
    unittest.main()
