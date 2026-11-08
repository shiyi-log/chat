import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PINNED_ACTIONS = {
    "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0",
    "actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131",
    "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9",
}


def load_workflow(path):
    parsed = subprocess.run(
        [
            "ruby",
            "-ryaml",
            "-rjson",
            "-e",
            "puts JSON.generate(YAML.safe_load(File.read(ARGV.fetch(0)), aliases: true))",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(parsed.stdout)


class CandidateReleaseWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ci = load_workflow(ROOT / ".github/workflows/ci.yml")
        cls.desktop = load_workflow(ROOT / ".github/workflows/desktop-build.yml")

    def test_preview_release_is_tag_scoped_and_waits_for_all_platform_builds(self):
        triggers = self.ci.get("on", self.ci.get(True, self.ci.get("true")))
        self.assertEqual(["v*-preview.*"], triggers["push"].get("tags"))
        jobs = self.ci["jobs"]
        self.assertIn("candidate-package", jobs)
        self.assertIn("candidate-release", jobs)
        self.assertEqual(
            {
                "repository",
                "server",
                "server-build-preview",
                "web-build-preview",
                "android-compile",
                "android-emulator-smoke",
                "ios-simulator-build",
                "desktop-build-preview",
            },
            set(jobs["candidate-package"]["needs"]),
        )
        self.assertEqual("candidate-package", jobs["candidate-release"]["needs"])
        self.assertIn("startsWith(github.ref_name, 'v')", jobs["candidate-package"]["if"])
        self.assertIn("-preview.", jobs["candidate-package"]["if"])

    def test_only_the_existing_tag_draft_release_job_has_write_permission(self):
        jobs = self.ci["jobs"]
        self.assertIn("candidate-release", jobs)
        self.assertEqual({"contents": "read"}, self.ci["permissions"])
        for name, job in jobs.items():
            if name != "candidate-release":
                self.assertNotEqual("write", job.get("permissions", {}).get("contents"), name)

        release = jobs["candidate-release"]
        self.assertEqual({"contents": "write"}, release["permissions"])
        self.assertEqual(
            "${{ github.token }}",
            next(step for step in release["steps"] if step.get("name") == "Create or resume draft preview release")["env"]["GH_TOKEN"],
        )
        commands = "\n".join(step.get("run", "") for step in release["steps"])
        self.assertIn("sha256sum --check SHA256SUMS", commands)
        self.assertIn("gh release create", commands)
        self.assertIn("gh release upload", commands)
        self.assertIn("--clobber", commands)
        self.assertIn('if [ "${tag_sha}" != "${GITHUB_SHA}" ]', commands)
        self.assertIn("Workflow run ID:", commands)
        self.assertIn("jq -e", commands)
        self.assertIn("--verify-tag", commands)
        self.assertIn("--draft", commands)
        self.assertIn("--prerelease", commands)
        self.assertNotIn("checkout@", "\n".join(step.get("uses", "") for step in release["steps"]))

    def test_candidate_transport_actions_are_pinned_to_reviewed_commits(self):
        jobs = self.ci["jobs"]
        actual = {
            step["uses"]
            for job_name in ("candidate-package", "candidate-release")
            for step in jobs[job_name]["steps"]
            if step.get("uses", "").startswith("actions/")
        }
        self.assertEqual(PINNED_ACTIONS, actual)

    def test_main_desktop_changes_build_all_debug_platforms(self):
        triggers = self.desktop.get("on", self.desktop.get(True, self.desktop.get("true")))
        self.assertIn("workflow_call", triggers)
        self.assertEqual(["main"], triggers["push"]["branches"])
        self.assertEqual(
            {"clients/desktop/**", ".github/workflows/desktop-build.yml"},
            set(triggers["push"]["paths"]),
        )
        self.assertEqual(
            ["linux", "macos", "windows", "all"],
            triggers["workflow_dispatch"]["inputs"]["platform"]["options"],
        )
        self.assertEqual("string", triggers["workflow_call"]["inputs"]["platform"]["type"])
        self.assertTrue(triggers["workflow_call"]["inputs"]["platform"]["required"])
        for platform in ("linux", "macos", "windows"):
            job = self.desktop["jobs"][platform]
            self.assertIn("github.event_name == 'push'", job["if"])
            self.assertIn("github.ref == 'refs/heads/main'", job["if"])
            self.assertIn("self-hosted", job["runs-on"])
            artifact = next(step for step in job["steps"] if step.get("uses") == "actions/upload-artifact@v7")
            self.assertEqual(14, artifact["with"]["retention-days"])
            self.assertIn(".manifest.json", artifact["with"]["path"])

        self.assertIn("'all'", self.desktop["jobs"]["linux"]["if"])
        self.assertIn("'all'", self.desktop["jobs"]["macos"]["if"])
        self.assertIn("'all'", self.desktop["jobs"]["windows"]["if"])

        caller = self.ci["jobs"]["desktop-build-preview"]
        self.assertEqual("./.github/workflows/desktop-build.yml", caller["uses"])
        self.assertEqual("all", caller["with"]["platform"])

    def test_candidate_package_uploads_one_reviewable_bundle_and_checksum(self):
        self.assertIn("candidate-package", self.ci["jobs"])
        package = self.ci["jobs"]["candidate-package"]
        self.assertEqual(
            "${{ steps.upload_candidate.outputs.artifact-id }}",
            package["outputs"]["artifact_id"],
        )
        steps = package["steps"]
        commands = "\n".join(step.get("run", "") for step in steps)
        self.assertIn("tools/package_candidate_release.py", commands)
        self.assertTrue(
            any(
                step.get("uses") == "actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131"
                for step in steps
            )
        )
        upload = next(step for step in steps if step.get("name") == "Upload candidate release bundle")
        self.assertIn(upload["uses"], PINNED_ACTIONS)
        self.assertEqual("upload_candidate", upload["id"])
        self.assertEqual(
            "chat-candidate-release-${{ github.run_id }}-${{ github.run_attempt }}",
            upload["with"]["name"],
        )
        self.assertEqual("${{ runner.temp }}/chat-candidate-release/*", upload["with"]["path"])
        self.assertEqual(0, upload["with"]["compression-level"])
        self.assertEqual("error", upload["with"]["if-no-files-found"])

    def test_release_job_downloads_the_candidate_artifact_id_from_package_job(self):
        release = self.ci["jobs"]["candidate-release"]
        download = next(step for step in release["steps"] if step.get("name") == "Download checksummed candidate")
        self.assertEqual(
            "${{ needs.candidate-package.outputs.artifact_id }}",
            download["with"]["artifact-ids"],
        )
        self.assertEqual("download_candidate", download["id"])
        self.assertTrue(download["continue-on-error"])

        explain = next(
            step for step in release["steps"]
            if step.get("name") == "Explain how to recover a missing candidate"
        )
        self.assertEqual("steps.download_candidate.outcome != 'success'", explain["if"])
        self.assertIn("Re-run all jobs", explain["run"])

    def test_platform_artifact_names_are_scoped_to_run_and_attempt(self):
        expected = {
            ("server-build-preview", "Upload Linux server preview", "chat-server-linux-preview"),
            ("web-build-preview", "Upload Web preview", "chat-web-preview"),
            ("android-compile", "Upload Android debug APK preview", "chat-android-afat-debug"),
            ("ios-simulator-build", "Upload unsigned iOS simulator preview", "chat-ios-simulator-debug"),
        }
        for job_name, step_name, prefix in expected:
            with self.subTest(job=job_name):
                step = next(
                    item for item in self.ci["jobs"][job_name]["steps"]
                    if item.get("name") == step_name
                )
                self.assertEqual(
                    f"{prefix}-${{{{ github.run_id }}}}-${{{{ github.run_attempt }}}}",
                    step["with"]["name"],
                )

        for platform in ("linux", "macos", "windows"):
            with self.subTest(platform=platform):
                step = next(
                    item for item in self.desktop["jobs"][platform]["steps"]
                    if item.get("name", "").startswith("Upload ")
                )
                self.assertIn("${{ github.run_id }}-${{ github.run_attempt }}", step["with"]["name"])


if __name__ == "__main__":
    unittest.main()
