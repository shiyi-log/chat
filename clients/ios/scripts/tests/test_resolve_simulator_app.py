import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "resolve_simulator_app.py"


class ResolveSimulatorAppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.products = Path(self.directory.name) / "Debug-iphonesimulator"
        self.products.mkdir()

    def create_app(self, relative_path, **overrides):
        app = self.products / relative_path
        app.mkdir(parents=True)
        metadata = {
            "CFBundleIdentifier": "com.privatechat.ios",
            "CFBundleSupportedPlatforms": ["iPhoneSimulator"],
            "DTPlatformName": "iphonesimulator",
        }
        metadata.update(overrides)
        with (app / "Info.plist").open("wb") as handle:
            plistlib.dump(metadata, handle)
        return app

    def run_resolver(self, path=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(path or self.products)],
            text=True,
            capture_output=True,
        )

    def test_resolves_flat_xcode_app(self):
        app = self.create_app("Telegram.app")
        result = self.run_resolver()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(app.resolve()) + "\n", result.stdout)

    def test_resolves_nested_bazel_app(self):
        app = self.create_app("bazel-out/ios_sim_arm64-dbg/bin/Telegram/Telegram.app")
        result = self.run_resolver()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(app.resolve()) + "\n", result.stdout)

    def test_accepts_an_explicit_app_path(self):
        app = self.create_app("Telegram.app")
        result = self.run_resolver(app)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(app.resolve()) + "\n", result.stdout)

    def test_flat_symlink_to_bazel_app_is_one_actual_candidate(self):
        app = self.create_app("bazel-out/ios_sim_arm64-dbg/bin/Telegram/Telegram.app")
        (self.products / "Telegram.app").symlink_to(app, target_is_directory=True)
        result = self.run_resolver()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(app.resolve()) + "\n", result.stdout)

    def test_missing_app_fails_without_stdout(self):
        result = self.run_resolver()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("no simulator app", result.stderr.lower())

    def test_two_actual_apps_fail_instead_of_selecting_a_stale_build(self):
        self.create_app("bazel-out/ios_sim_arm64-dbg/bin/Telegram/Telegram.app")
        self.create_app("bazel-out/ios_sim_x86_64-dbg/bin/Telegram/Telegram.app")
        result = self.run_resolver()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("ambiguous", result.stderr.lower())

    def test_foreign_bundle_is_not_archived_as_chat(self):
        self.create_app("Telegram.app", CFBundleIdentifier="org.telegram.Telegram")
        result = self.run_resolver()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("bundle identifier", result.stderr.lower())

    def test_device_app_is_not_archived_as_simulator_app(self):
        self.create_app(
            "Telegram.app",
            CFBundleSupportedPlatforms=["iPhoneOS"],
            DTPlatformName="iphoneos",
        )
        result = self.run_resolver()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("iphonesimulator", result.stderr.lower())

    def test_missing_or_malformed_metadata_fails_explicitly(self):
        app = self.create_app("Telegram.app")
        for content in (None, b"invalid plist"):
            with self.subTest(content=content):
                plist = app / "Info.plist"
                if content is None:
                    plist.unlink()
                else:
                    plist.write_bytes(content)
                result = self.run_resolver()
                self.assertNotEqual(0, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertIn("Info.plist", result.stderr)


if __name__ == "__main__":
    unittest.main()
