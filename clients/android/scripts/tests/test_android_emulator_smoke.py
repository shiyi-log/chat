import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "smoke_android_emulator.py"


class AndroidEmulatorSmokeTests(unittest.TestCase):
    def test_chinese_first_launch_hierarchy_passes_and_english_fallback_fails(self):
        chinese = '<hierarchy><node text="开始聊天" content-desc="" /></hierarchy>'
        english = '<hierarchy><node text="Start Messaging" content-desc="" /></hierarchy>'

        with tempfile.TemporaryDirectory() as directory:
            chinese_path = Path(directory) / "chinese.xml"
            english_path = Path(directory) / "english.xml"
            chinese_path.write_text(chinese, encoding="utf-8")
            english_path.write_text(english, encoding="utf-8")

            chinese_result = subprocess.run(
                [sys.executable, str(SCRIPT), "--check-hierarchy", str(chinese_path)],
                capture_output=True,
                text=True,
            )
            english_result = subprocess.run(
                [sys.executable, str(SCRIPT), "--check-hierarchy", str(english_path)],
                capture_output=True,
                text=True,
            )

        self.assertEqual(0, chinese_result.returncode, chinese_result.stdout + chinese_result.stderr)
        self.assertNotEqual(0, english_result.returncode)
        self.assertIn("Simplified Chinese", english_result.stderr)


if __name__ == "__main__":
    unittest.main()
