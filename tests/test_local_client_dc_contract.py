import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_MTPROTO_PORT = "25222"


class LocalClientDcContractTest(unittest.TestCase):
    def test_android_emulator_uses_local_runtime_mtproto_port(self):
        source = (
            ROOT / "clients/android/TMessagesProj/jni/tgnet/ConnectionsManager.cpp"
        ).read_text(encoding="utf-8")
        ports = re.findall(
            r'addAddressAndPort\("10\.0\.2\.2",\s*(\d+),\s*0,\s*""\)',
            source,
        )

        self.assertEqual(2, len(ports))
        self.assertEqual({LOCAL_MTPROTO_PORT}, set(ports))

    def test_desktop_loopback_dc_uses_local_runtime_mtproto_port(self):
        source = (
            ROOT
            / "clients/desktop/Telegram/SourceFiles/mtproto/mtproto_dc_options.cpp"
        ).read_text(encoding="utf-8")
        ports = re.findall(
            r'\{\s*1,\s*"(?:127\.0\.0\.1|::1)",\s*(\d+)\s*\}', source
        )

        self.assertEqual(4, len(ports))
        self.assertEqual({LOCAL_MTPROTO_PORT}, set(ports))

    def test_ios_seed_dc_uses_local_runtime_mtproto_port(self):
        source = (
            ROOT
            / "clients/ios/submodules/TelegramCore/Sources/Network/Network.swift"
        ).read_text(encoding="utf-8")
        ports = re.findall(r"MTDatacenterAddress\(ip: \$0, port: (\d+)", source)

        self.assertEqual([LOCAL_MTPROTO_PORT], ports)


if __name__ == "__main__":
    unittest.main()
