import ast
import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPRODUCER = """\
import Foundation

final class Owner {
    var handler: (() -> Void)?

    func setup() {
        self.handler = {
            let nested: () -> Void = { [weak self] in
                self?.handler = nil
            }
            nested()
        }
    }
}
"""


class TelegramCoreSwiftWarningTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("swiftc"), "Swift compiler is required")
    def test_swift_5_implicit_capture_warning_is_downgraded_for_strict_targets(self):
        strict_targets = (
            "submodules/TelegramCore",
            "submodules/SolidRoundedButtonNode",
            "submodules/InAppPurchaseManager",
            "submodules/TelegramVoip",
            "submodules/MediaPlayer",
            "submodules/TelegramUI/Components/AudioWaveformComponent",
            "submodules/TelegramUI/Components/Calls/CallScreen",
        )
        for target in strict_targets:
            with self.subTest(target=target):
                build_file = (ROOT / target / "BUILD").read_text(encoding="utf-8")
                copts_match = re.search(r"copts\s*=\s*(\[[\s\S]*?\])", build_file)
                self.assertIsNotNone(copts_match, f"{target} must declare Swift compiler options")
                copts = ast.literal_eval(copts_match.group(1))
                self.assertIn("-warnings-as-errors", copts)
                self.assertIn("-Wwarning", copts)
                self.assertIn("ImplicitStrongCapture", copts)

                result = subprocess.run(
                    ["swiftc", "-typecheck", "-swift-version", "5", *copts, "-"],
                    input=REPRODUCER,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("ImplicitStrongCapture", result.stderr)
                self.assertIn("warning:", result.stderr)

    def test_animated_sticker_jpeg_type_uses_uniform_type_identifiers(self):
        source = (ROOT / "submodules/TelegramAnimatedStickerNode/Sources/AnimatedStickerUtils.swift").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("kUTTypeJPEG", source)
        self.assertIn("import UniformTypeIdentifiers", source)
        self.assertEqual(source.count("UTType.jpeg.identifier as CFString"), 2)

    def test_location_authorization_uses_instance_status_api(self):
        source_files = (
            "submodules/DeviceAccess/Sources/DeviceAccess.swift",
            "submodules/DeviceAccess/Sources/LocationManager.swift",
            "submodules/LocationUI/Sources/LocationPickerControllerNode.swift",
            "submodules/WebUI/Sources/WebAppController.swift",
        )
        for relative_path in source_files:
            with self.subTest(source=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertNotIn("CLLocationManager.authorizationStatus()", source, relative_path)


if __name__ == "__main__":
    unittest.main()
