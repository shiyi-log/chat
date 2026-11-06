#!/usr/bin/env python3
"""Guard the public Android source tree against reusing its shared test signer."""
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULES = (
    "TMessagesProj_App/build.gradle",
    "TMessagesProj_AppStandalone/build.gradle",
    "TMessagesProj_AppHuawei/build.gradle",
    "TMessagesProj_AppTests/build.gradle",
    "TMessagesProj_AppHockeyApp/build.gradle",
)
SIGNING_PROPERTIES = (
    "RELEASE_STORE_FILE",
    "RELEASE_STORE_PASSWORD",
    "RELEASE_KEY_ALIAS",
    "RELEASE_KEY_PASSWORD",
)


class PrivateChatSigningConfigTests(unittest.TestCase):
    def test_release_signing_values_are_not_committed(self):
        properties = (ROOT / "gradle.properties").read_text(encoding="utf-8")
        for name in SIGNING_PROPERTIES:
            with self.subTest(name=name):
                has_value = re.search(rf"(?m)^\s*{name}\s*=\s*\S+", properties) is not None
                self.assertFalse(has_value, f"{name} must be supplied outside tracked Gradle properties")

    def test_shared_signing_script_requires_all_external_values(self):
        script = (ROOT / "private-chat-signing.gradle").read_text(encoding="utf-8")
        has_all_properties = all(f'"{name}"' in script for name in SIGNING_PROPERTIES)
        has_artifact_guard = "gradle.taskGraph.whenReady" in script
        self.assertTrue(has_all_properties, "the shared signer must read all four external properties")
        self.assertTrue(has_artifact_guard, "distribution tasks must be blocked when release signing is absent")

    def test_shared_release_keystore_is_not_tracked(self):
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "TMessagesProj/config/release.keystore"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(0, result.returncode, "the shared test keystore must stay local")

    def test_app_variants_do_not_use_the_shared_keystore(self):
        for relative_path in MODULES:
            with self.subTest(module=relative_path):
                contents = (ROOT / relative_path).read_text(encoding="utf-8")
                uses_shared_keystore = "TMessagesProj/config/release.keystore" in contents
                uses_private_release_signing = "privateChatReleaseSigning" in contents
                declares_custom_debug_signing = re.search(r"(?s)signingConfigs\s*\{\s*debug\s*\{", contents) is not None
                self.assertFalse(uses_shared_keystore, f"{relative_path} must not use the shared test keystore")
                self.assertTrue(
                    uses_private_release_signing,
                    f"{relative_path} must use externally configured release signing",
                )
                self.assertFalse(declares_custom_debug_signing, f"{relative_path} must use Android's default debug signer")


if __name__ == "__main__":
    unittest.main()
