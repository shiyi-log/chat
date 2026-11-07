#!/usr/bin/env python3
import json
import plistlib
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("package_desktop_debug.py")
WORKFLOW = SCRIPT.parents[3] / ".github" / "workflows" / "desktop-build.yml"


class PackageDesktopDebugTests(unittest.TestCase):
    def test_linux_build_mounts_dependency_cache_targets(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            '--volume "${RUNNER_WORKSPACE}/desktop-build-cache/chat/linux/Libraries:/usr/src/Libraries"',
            workflow,
        )
        self.assertIn(
            '--volume "${RUNNER_WORKSPACE}/desktop-build-cache/chat/linux/ThirdParty:/usr/src/ThirdParty"',
            workflow,
        )

    def test_linux_package_contains_debug_binary_and_signature_manifest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            build = root / "out" / "Debug"
            build.mkdir(parents=True)
            (build / "Chat").write_bytes(b"debug binary")
            (build / "libsample.so").write_bytes(b"runtime library")
            archive = root / "chat-linux-debug.tar.gz"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--platform",
                    "linux",
                    "--build-dir",
                    str(build),
                    "--output",
                    str(archive),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            with tarfile.open(archive, "r:gz") as packaged:
                self.assertEqual(
                    {"Chat", "libsample.so", "build-manifest.json"},
                    set(packaged.getnames()),
                )
                manifest = json.load(packaged.extractfile("build-manifest.json"))
            self.assertEqual("linux", manifest["platform"])
            self.assertEqual("Debug", manifest["configuration"])
            self.assertEqual("not-applicable", manifest["signing"]["status"])

    def test_package_fails_when_debug_application_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            build = root / "out" / "Debug"
            build.mkdir(parents=True)
            archive = root / "chat-linux-debug.tar.gz"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--platform",
                    "linux",
                    "--build-dir",
                    str(build),
                    "--output",
                    str(archive),
                ],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("Debug application not found", result.stderr)
            self.assertFalse(archive.exists())

    @unittest.skipUnless(sys.platform == "win32", "Authenticode is available on Windows runners.")
    def test_windows_package_records_the_executable_authenticode_status(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            build = root / "out" / "Debug"
            build.mkdir(parents=True)
            (build / "Chat.exe").write_bytes(b"unsigned test executable")
            archive = root / "chat-windows-debug.zip"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--platform",
                    "windows",
                    "--build-dir",
                    str(build),
                    "--output",
                    str(archive),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            with zipfile.ZipFile(archive) as packaged:
                self.assertIn("Chat.exe", packaged.namelist())
                manifest = json.loads(packaged.read("build-manifest.json"))
            self.assertEqual("NotSigned", manifest["signing"]["status"])

    @unittest.skipUnless(sys.platform == "darwin", "macOS app bundles require codesign and ditto.")
    def test_macos_package_preserves_bundle_and_records_invalid_signature_status(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            build = root / "out" / "Debug"
            executable = build / "Chat.app" / "Contents" / "MacOS" / "Chat"
            executable.parent.mkdir(parents=True)
            with executable.open("wb") as output:
                subprocess.run(
                    ["cc", "-x", "c", "-o", str(executable), "-"],
                    input="int main(void) { return 0; }\n",
                    text=True,
                    check=True,
                    stdout=output,
                )
            plist_path = executable.parents[1] / "Info.plist"
            with plist_path.open("wb") as plist_file:
                plistlib.dump(
                    {
                        "CFBundleExecutable": "Chat",
                        "CFBundleIdentifier": "com.privatechat.desktop.debug",
                        "CFBundleName": "Chat",
                        "CFBundlePackageType": "APPL",
                    },
                    plist_file,
                )
            archive = root / "chat-macos-debug.zip"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--platform",
                    "macos",
                    "--build-dir",
                    str(build),
                    "--output",
                    str(archive),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            manifest = json.loads(Path(str(archive) + ".manifest.json").read_text())
            self.assertEqual(
                "invalid-or-unverifiable",
                manifest["signing"]["status"],
                manifest["signing"],
            )
            with zipfile.ZipFile(archive) as packaged:
                self.assertTrue(any(name.endswith("Chat.app/Contents/MacOS/Chat") for name in packaged.namelist()))


if __name__ == "__main__":
    unittest.main()
