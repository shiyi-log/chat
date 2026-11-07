import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/package_candidate_release.py"
RUN_ID = "42406224293"
RUN_ATTEMPT = "1"
REVISION = "da353e4a62d0e16a2cc39737f501b77474336c91"
SERVER_BINARIES = (
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


def tar_gz(files):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, contents in files.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(contents)
            archive.addfile(entry, io.BytesIO(contents))
    return output.getvalue()


def zip_bytes(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, contents in files.items():
            archive.writestr(name, contents)
    return output.getvalue()


def write_artifact(root, artifact_name, files):
    artifact_dir = root / artifact_name
    for name, contents in files.items():
        path = artifact_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    return artifact_dir


def desktop_manifest(platform):
    return {
        "platform": platform,
        "configuration": "Debug",
        "source_revision": REVISION,
        "signing": {"status": "unsigned"},
        "files": [],
    }


def create_artifacts(root, attempt=RUN_ATTEMPT, run_id=RUN_ID):
    suffix = f"{run_id}-{attempt}"
    write_artifact(
        root,
        f"chat-server-linux-preview-{suffix}",
        {"chat-server-linux-preview.tar.gz": tar_gz({name: b"binary" for name in SERVER_BINARIES})},
    )
    write_artifact(
        root,
        f"chat-web-preview-{suffix}",
        {"index.html": b"<main>preview</main>", "assets/app.js": b"web bundle"},
    )
    write_artifact(
        root,
        f"chat-android-afat-debug-{suffix}",
        {"app.apk": zip_bytes({"AndroidManifest.xml": b"manifest", "classes.dex": b"dex"})},
    )
    write_artifact(
        root,
        f"chat-ios-simulator-debug-{suffix}",
        {
            "Chat-iOS-Simulator.zip": zip_bytes(
                {"Chat.app/Info.plist": b"plist", "Chat.app/Chat": b"simulator app"}
            )
        },
    )
    desktop_payloads = {
        "linux": (
            "tar.gz",
            tar_gz(
                {
                    "Chat": b"linux binary",
                    "build-manifest.json": json.dumps(desktop_manifest("linux")).encode(),
                }
            ),
        ),
        "macos": (
            "zip",
            zip_bytes(
                {
                    "Chat.app/Contents/Info.plist": b"plist",
                    "Chat.app/Contents/MacOS/Chat": b"macOS binary",
                }
            ),
        ),
        "windows": (
            "zip",
            zip_bytes(
                {
                    "Chat.exe": b"windows binary",
                    "build-manifest.json": json.dumps(desktop_manifest("windows")).encode(),
                }
            ),
        ),
    }
    for platform, (extension, payload) in desktop_payloads.items():
        name = f"chat-desktop-{platform}-debug-{suffix}"
        write_artifact(
            root,
            name,
            {
                f"{name}.{extension}": payload,
                f"{name}.{extension}.manifest.json": json.dumps(desktop_manifest(platform)).encode(),
            },
        )


def run_packager(
    artifacts,
    output,
    tag="v0.1.0-preview.1",
    run_attempt=RUN_ATTEMPT,
    run_id=RUN_ID,
):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--artifacts-dir",
            str(artifacts),
            "--output-dir",
            str(output),
            "--tag",
            tag,
            "--revision",
            REVISION,
            "--run-id",
            run_id,
            "--run-attempt",
            run_attempt,
        ],
        capture_output=True,
        text=True,
    )


class CandidateReleasePackageTests(unittest.TestCase):
    def test_candidate_assets_include_each_platform_manifest_and_checksum(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = root / "artifacts"
            output = root / "output"
            artifacts.mkdir()
            create_artifacts(artifacts)

            result = run_packager(artifacts, output)

            self.assertEqual(0, result.returncode, result.stderr)
            expected_assets = {
                "chat-server-linux-preview.tar.gz",
                "chat-web-preview.zip",
                "chat-android-afat-debug.apk",
                "chat-ios-simulator-debug.zip",
                "chat-desktop-linux-debug-42406224293-1.tar.gz",
                "chat-desktop-macos-debug-42406224293-1.zip",
                "chat-desktop-windows-debug-42406224293-1.zip",
                "README.md",
                "build-manifest.json",
                "SHA256SUMS",
            }
            self.assertEqual(expected_assets, {path.name for path in output.iterdir()})

            checksums = {}
            for line in (output / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
                checksum, filename = line.split("  ", 1)
                checksums[filename] = checksum
            self.assertEqual(expected_assets - {"SHA256SUMS"}, set(checksums))
            for filename, expected_hash in checksums.items():
                self.assertEqual(expected_hash, hashlib.sha256((output / filename).read_bytes()).hexdigest())

            manifest = json.loads((output / "build-manifest.json").read_text(encoding="utf-8"))
            readme = (output / "README.md").read_text(encoding="utf-8")
            self.assertEqual("v0.1.0-preview.1", manifest["tag"])
            self.assertEqual(REVISION, manifest["source_revision"])
            self.assertEqual("unsigned-preview", manifest["release_type"])
            self.assertEqual(RUN_ATTEMPT, manifest["workflow_run_attempt"])
            self.assertEqual(7, len(manifest["artifacts"]))
            self.assertEqual(
                {"linux", "macos", "windows"},
                set(manifest["desktop_builds"]),
            )
            for desktop in manifest["desktop_builds"].values():
                self.assertEqual("unsigned", desktop["signing"]["status"])
                self.assertEqual(REVISION, desktop["source_revision"])

            web_assets = set(zipfile.ZipFile(output / "chat-web-preview.zip").namelist())
            self.assertIn("index.html", web_assets)
            self.assertIn("assets/app.js", web_assets)
            self.assertIn("iOS 模拟器", readme)
            self.assertIn("afatDebug", readme)
            self.assertIn("短信服务", readme)

    def test_retry_uses_latest_platform_artifacts_from_the_same_workflow_run(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = root / "artifacts"
            output = root / "output"
            artifacts.mkdir()
            create_artifacts(artifacts, attempt="1")

            result = run_packager(artifacts, output, run_attempt="2")

            self.assertEqual(0, result.returncode, result.stderr)
            manifest = json.loads((output / "build-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("2", manifest["workflow_run_attempt"])
            self.assertIn("chat-desktop-linux-debug-42406224293-1.tar.gz", {p.name for p in output.iterdir()})
            self.assertEqual(
                {"1"},
                {artifact["source_workflow_run_attempt"] for artifact in manifest["artifacts"]},
            )

    def test_retry_can_combine_latest_available_attempt_for_each_platform(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = root / "artifacts"
            output = root / "output"
            artifacts.mkdir()
            create_artifacts(artifacts, attempt="1")
            create_artifacts(artifacts, attempt="2")
            for prefix in (
                "chat-web-preview",
                "chat-ios-simulator-debug",
                "chat-desktop-macos-debug",
                "chat-desktop-windows-debug",
            ):
                shutil.rmtree(artifacts / f"{prefix}-{RUN_ID}-2")

            result = run_packager(artifacts, output, run_attempt="2")

            self.assertEqual(0, result.returncode, result.stderr)
            manifest = json.loads((output / "build-manifest.json").read_text(encoding="utf-8"))
            attempts = {
                artifact["name"]: artifact["source_workflow_run_attempt"]
                for artifact in manifest["artifacts"]
            }
            self.assertEqual(
                {
                    "server-linux-preview": "2",
                    "web-preview": "1",
                    "android-afat-debug": "2",
                    "ios-simulator-debug": "1",
                    "desktop-linux-debug": "2",
                    "desktop-macos-debug": "1",
                    "desktop-windows-debug": "1",
                },
                attempts,
            )

    def test_attempt_selection_uses_numeric_order(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = root / "artifacts"
            output = root / "output"
            artifacts.mkdir()
            create_artifacts(artifacts, attempt="9")
            create_artifacts(artifacts, attempt="10")

            result = run_packager(artifacts, output, run_attempt="10")

            self.assertEqual(0, result.returncode, result.stderr)
            manifest = json.loads((output / "build-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                {"10"},
                {artifact["source_workflow_run_attempt"] for artifact in manifest["artifacts"]},
            )

    def test_artifacts_from_another_run_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = root / "artifacts"
            output = root / "output"
            artifacts.mkdir()
            create_artifacts(artifacts, run_id="99999999999")

            result = run_packager(artifacts, output)

            self.assertNotEqual(0, result.returncode)
            self.assertIn("missing CI artifact for this workflow run", result.stderr)
            self.assertFalse(output.exists())

    def test_artifact_from_a_future_attempt_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = root / "artifacts"
            output = root / "output"
            artifacts.mkdir()
            create_artifacts(artifacts, attempt="2")

            result = run_packager(artifacts, output, run_attempt="1")

            self.assertNotEqual(0, result.returncode)
            self.assertIn("missing CI artifact for this workflow run", result.stderr)
            self.assertFalse(output.exists())

    def test_corrupt_native_archive_is_rejected_without_partial_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = root / "artifacts"
            output = root / "output"
            artifacts.mkdir()
            create_artifacts(artifacts)
            (artifacts / f"chat-android-afat-debug-{RUN_ID}-{RUN_ATTEMPT}/app.apk").write_bytes(
                b"not an APK archive"
            )

            result = run_packager(artifacts, output)

            self.assertNotEqual(0, result.returncode)
            self.assertIn("APK", result.stderr)
            self.assertFalse(output.exists())

    def test_stable_tags_are_rejected_before_creating_release_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = root / "artifacts"
            output = root / "output"
            artifacts.mkdir()
            create_artifacts(artifacts)

            result = run_packager(artifacts, output, tag="v1.0.0")

            self.assertNotEqual(0, result.returncode)
            self.assertIn("preview tag", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
