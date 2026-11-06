import sys
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


IOS_ROOT = Path(__file__).resolve().parents[2]
MAKE_ROOT = IOS_ROOT / "build-system" / "Make"
sys.path.insert(0, str(MAKE_ROOT))

import Make


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


if __name__ == "__main__":
    unittest.main()
