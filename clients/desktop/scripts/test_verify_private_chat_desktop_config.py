import os
import subprocess
import sys
import unittest
from pathlib import Path


VERIFIER_PATH = Path(__file__).with_name("verify_private_chat_desktop_config.py")


class DesktopConfigOutputTests(unittest.TestCase):
    def test_verifier_completes_when_stdout_uses_cp1252(self):
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "cp1252"
        result = subprocess.run(
            [sys.executable, str(VERIFIER_PATH)],
            capture_output=True,
            env=environment,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr.decode("cp1252", errors="replace"))
        self.assertNotIn(b"UnicodeEncodeError", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
