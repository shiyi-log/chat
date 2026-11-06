import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_MTPROTO_PORT = "35222"


class LocalClientDcContractTest(unittest.TestCase):
    def test_android_emulator_uses_local_runtime_mtproto_port(self):
        source = (
            ROOT / "clients/android/TMessagesProj/jni/tgnet/ConnectionsManager.cpp"
        ).read_text(encoding="utf-8")
        build_gradle = (
            ROOT / "clients/android/TMessagesProj/build.gradle"
        ).read_text(encoding="utf-8")
        cmake = (
            ROOT / "clients/android/TMessagesProj/jni/CMakeLists.txt"
        ).read_text(encoding="utf-8")

        self.assertEqual(2, source.count('addAddressAndPort("10.0.2.2", privateChatDcPort, 0, "")'))
        self.assertIn("constexpr int privateChatDcPort = PRIVATE_CHAT_LOCAL_DC_PORT;", source)
        self.assertIn("constexpr int privateChatDcPort = 25222;", source)
        self.assertIn(f'arguments "-DPRIVATE_CHAT_LOCAL_DC_PORT={LOCAL_MTPROTO_PORT}"', build_gradle)
        self.assertIn("if (DEFINED PRIVATE_CHAT_LOCAL_DC_PORT)", cmake)
        self.assertIn(
            "target_compile_definitions(tgnet PRIVATE PRIVATE_CHAT_LOCAL_DC_PORT=${PRIVATE_CHAT_LOCAL_DC_PORT})",
            cmake,
        )

    def test_desktop_loopback_dc_uses_local_runtime_mtproto_port(self):
        source = (
            ROOT
            / "clients/desktop/Telegram/SourceFiles/mtproto/mtproto_dc_options.cpp"
        ).read_text(encoding="utf-8")
        cmake = (
            ROOT / "clients/desktop/Telegram/cmake/td_mtproto.cmake"
        ).read_text(encoding="utf-8")

        self.assertEqual(4, source.count("PRIVATE_CHAT_DC_PORT }"))
        self.assertIn("#define PRIVATE_CHAT_DC_PORT 25222", source)
        self.assertIn(
            f"set(PRIVATE_CHAT_LOCAL_DC_PORT {LOCAL_MTPROTO_PORT} CACHE STRING",
            cmake,
        )
        self.assertIn(
            '"$<$<CONFIG:Debug>:PRIVATE_CHAT_DC_PORT=${PRIVATE_CHAT_LOCAL_DC_PORT}>"',
            cmake,
        )

    def test_ios_seed_dc_uses_local_runtime_mtproto_port(self):
        source = (
            ROOT
            / "clients/ios/submodules/TelegramCore/Sources/Network/Network.swift"
        ).read_text(encoding="utf-8")
        debug_release_ports = re.search(
            r"#if DEBUG\s+let localSeedPort = (\d+)\s+#else\s+let localSeedPort = (\d+)\s+#endif",
            source,
        )

        self.assertIsNotNone(debug_release_ports)
        self.assertEqual(
            (LOCAL_MTPROTO_PORT, "25222"), debug_release_ports.groups()
        )
        self.assertIn("MTDatacenterAddress(ip: $0, port: localSeedPort", source)


if __name__ == "__main__":
    unittest.main()
