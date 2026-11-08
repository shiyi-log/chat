import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


IOS_ROOT = Path(__file__).resolve().parents[2]
MAKE_ROOT = IOS_ROOT / "build-system" / "Make"
sys.path.insert(0, str(MAKE_ROOT))

import Make
import BazelLocation


class MakeProjectGenerationTests(unittest.TestCase):
    def test_rules_xcodeproj_template_is_versioned_and_not_ignored(self):
        template = (
            IOS_ROOT
            / "build-system/bazel-rules/rules_xcodeproj/xcodeproj/internal/templates/xcodeproj.bazelrc"
        )
        self.assertTrue(template.is_file(), "rules_xcodeproj requires its bazelrc template")
        self.assertNotEqual("", template.read_text().strip())

        result = subprocess.run(
            ["git", "check-ignore", "-q", str(template)],
            cwd=IOS_ROOT,
            check=False,
        )
        self.assertNotEqual(0, result.returncode, "required rules_xcodeproj template must not be ignored")

    def test_headless_generation_does_not_terminate_or_open_xcode(self):
        arguments = SimpleNamespace(
            overrideBazelVersion=False,
            overrideXcodeVersion=True,
            bazelUserRoot=None,
            cacheDir="/tmp/private-chat-ios-cache",
            cacheHost=None,
            continueOnError=False,
            buildNumber=10000,
            disableExtensions=True,
            disableProvisioningProfiles=True,
            projectIncludeRelease=False,
            xcodeManagedCodesigning=False,
            generateDsym=False,
            target=None,
            noOpen=True,
        )

        with (
            patch("Make.BazelCommandLine") as command_line,
            patch("Make.resolve_configuration"),
            patch("Make.generate", return_value="Telegram/Telegram.xcodeproj"),
            patch("Make.run_executable_with_output"),
            patch("Make.call_executable") as call_executable,
        ):
            command_line.return_value.get_project_generation_arguments.return_value = []

            Make.generate_project("/tmp/bazel", arguments)

        call_executable.assert_not_called()


class BazelLocationTests(unittest.TestCase):
    def test_download_uses_official_bazel_release_host(self):
        with tempfile.TemporaryDirectory() as directory:
            base_path = Path(directory) / "ios"
            base_path.mkdir()
            payload = b"verified bazel binary"
            expected_digest = hashlib.sha256(payload).hexdigest()

            def write_download(arguments, **kwargs):
                output_path = Path(arguments[arguments.index("--output") + 1])
                output_path.write_bytes(payload)

            versions = SimpleNamespace(
                bazel_version="8.4.2",
                bazel_version_sha256=expected_digest,
            )
            with (
                patch("BazelLocation.BuildEnvironmentVersions", return_value=versions),
                patch("BazelLocation.is_apple_silicon", return_value=True),
                patch("BazelLocation.call_executable", side_effect=write_download) as call_executable,
            ):
                BazelLocation.locate_bazel(str(base_path), None, None)

            download_command = call_executable.call_args.args[0]
            self.assertIn(
                "https://releases.bazel.build/8.4.2/release/bazel-8.4.2-darwin-arm64",
                download_command,
            )

    def test_invalid_download_is_not_copied_into_the_bazel_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            base_path = Path(directory) / "ios"
            base_path.mkdir()
            cache_path = Path(directory) / "cache"
            expected_digest = "a" * 64

            def write_invalid_download(arguments, **kwargs):
                output_path = Path(arguments[arguments.index("--output") + 1])
                output_path.write_bytes(b"HTTP error response")

            versions = SimpleNamespace(
                bazel_version="8.4.2",
                bazel_version_sha256=expected_digest,
            )
            with (
                patch("BazelLocation.BuildEnvironmentVersions", return_value=versions),
                patch("BazelLocation.is_apple_silicon", return_value=True),
                patch("BazelLocation.call_executable", side_effect=write_invalid_download),
                self.assertRaisesRegex(RuntimeError, "SHA256"),
            ):
                BazelLocation.locate_bazel(str(base_path), None, str(cache_path))

            cache_file = cache_path / "cas" / expected_digest[:2] / expected_digest
            self.assertFalse(cache_file.exists())


if __name__ == "__main__":
    unittest.main()
