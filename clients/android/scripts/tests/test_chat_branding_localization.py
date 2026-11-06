#!/usr/bin/env python3
"""Regression tests for Chat branding and the built-in Simplified Chinese path."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "TMessagesProj/src/main/res"
ANDROID = "{http://schemas.android.com/apk/res/android}"
CORE_KEYS = {
    "AppName", "AppNameBeta", "LanguageName", "LanguageNameInEnglish", "LanguageCode",
    "ContinueOnThisLanguage", "YourPhone", "StartText", "YourNumber", "PhoneNumber",
    "ChooseCountry", "ConfirmCorrectNumber", "YourCode", "SentSmsCode", "SentAppCode",
    "SentAppCodeTitle", "SentSmsCodeTitle", "WrongCode", "DidNotGetTheCode", "YourName",
    "FirstName", "LastName", "NoChats", "Search", "NewMessageTitle", "Chats", "Contacts",
    "Calls", "Settings", "SavedMessages", "Notifications", "PrivacyTitle", "Devices",
    "Language", "PrivacySettings", "ChatSettings", "LogOut", "OK", "Cancel", "Done",
    "Edit", "Delete", "Send", "Retry", "Connecting", "WaitingForNetwork", "StartMessaging",
}
FORMATS = re.compile(r"%(?:\d+\$)?[-#+ 0,(]*\d*(?:\.\d+)?[a-zA-Z%]")
TELEGRAM_NAME = re.compile(
    r"telegram|телеграм\w*|телеграмм\w*|телеграмме|텔레그램|"
    r"تيليجرام|تيليغرام|تليجرام|تليغرام|تلغرام|تلگرام|تیلیگرام|"
    r"टेलीग्राम|టెలిగ్రామ్",
    re.IGNORECASE,
)
TELEGRAM_OWNED_HOSTS = (
    "telegram.org", "telegram.me", "telegram.dog", "t.me", "telegra.ph",
)
LINK_TARGET = re.compile(r"https?://[^\s<>\"'\\)]+", re.IGNORECASE)


def telegram_owned_targets(value):
    for target in LINK_TARGET.findall(value):
        host = (urlsplit(target).hostname or "").lower()
        if any(host == domain or host.endswith("." + domain) for domain in TELEGRAM_OWNED_HOSTS):
            yield target


def string_map(path):
    root = ET.parse(path).getroot()
    return {item.get("name"): "".join(item.itertext()) for item in root.findall("string")}


def jdk_tools():
    java_home = os.environ.get("JAVA_HOME")
    candidates = [
        (Path(java_home) / "bin" / "javac", Path(java_home) / "bin" / "java") if java_home else None,
        (Path("/Applications/PyCharm.app/Contents/jbr/Contents/Home/bin/javac"),
         Path("/Applications/PyCharm.app/Contents/jbr/Contents/Home/bin/java")),
    ]
    for candidate in candidates:
        if candidate and candidate[0].is_file() and candidate[1].is_file():
            return tuple(str(path) for path in candidate)
    javac, java = shutil.which("javac"), shutil.which("java")
    return (javac, java) if javac and java else None


class ChatBrandingLocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.english = string_map(RES / "values/strings.xml")
        cls.chinese_path = RES / "values-zh-rCN/strings.xml"
        cls.chinese = string_map(cls.chinese_path) if cls.chinese_path.exists() else {}

    def test_core_simplified_chinese_resources_are_local_and_format_compatible(self):
        missing = CORE_KEYS - self.chinese.keys()
        self.assertFalse(missing, f"missing core Chinese strings: {sorted(missing)}")
        for key in CORE_KEYS:
            with self.subTest(key=key):
                self.assertEqual(
                    sorted(FORMATS.findall(self.english[key])),
                    sorted(FORMATS.findall(self.chinese[key])),
                    f"format placeholders differ for {key}",
                )
        self.assertEqual("Chat", self.chinese["AppName"])
        self.assertEqual("Chat 测试版", self.chinese["AppNameBeta"])
        self.assertEqual("zh_CN", self.chinese["LanguageCode"])
        self.assertEqual("欢迎使用 Chat", self.chinese["NoChats"])
        self.assertEqual("聊天", self.chinese["Chats"])
        self.assertEqual("设置", self.chinese["Settings"])

    def test_login_activity_resources_are_local_and_format_compatible(self):
        login_activity = ROOT / "TMessagesProj/src/main/java/org/telegram/ui/LoginActivity.java"
        source = login_activity.read_text(encoding="utf-8")
        keys = set(re.findall(r"R[.]string[.]([A-Za-z0-9_]+)", source))
        missing = keys - self.chinese.keys()
        self.assertFalse(missing, f"missing LoginActivity Chinese strings: {sorted(missing)}")
        for key in keys:
            with self.subTest(key=key):
                self.assertEqual(
                    sorted(FORMATS.findall(self.english[key])),
                    sorted(FORMATS.findall(self.chinese[key])),
                    f"format placeholders differ for {key}",
                )

    def test_attachment_and_media_strings_are_local_and_format_compatible(self):
        keys = {
            key for key in self.english
            if key.startswith(("Attach", "GlobalAttach"))
        }
        missing = keys - self.chinese.keys()
        self.assertFalse(missing, f"missing attachment and media Chinese strings: {sorted(missing)}")
        for key in keys:
            with self.subTest(key=key):
                self.assertEqual(
                    sorted(FORMATS.findall(self.english[key])),
                    sorted(FORMATS.findall(self.chinese[key])),
                    f"format placeholders differ for {key}",
                )

    def test_default_install_uses_chat_brand_while_preserving_upstream_domain_names(self):
        self.assertEqual("Chat", self.english["AppName"])
        self.assertEqual("Chat Beta", self.english["AppNameBeta"])
        self.assertEqual("Welcome to Chat", self.english["NoChats"])
        for key in ("SentAppCode", "SentAppCodeWithPhone", "SentAppCodeTitle", "SentCallCode", "OtherLoginCode"):
            with self.subTest(key=key):
                self.assertNotRegex(self.english[key], re.compile(r"\b(?:Private Chat|Telegram)\b", re.I))
        old_product_brand = re.compile(r"\bPrivate Chat\b(?!s)")
        stale = {key: value for key, value in self.english.items() if old_product_brand.search(value)}
        self.assertFalse(stale, f"English resources still show the old product name: {sorted(stale)}")
        self.assertEqual("Chat Premium", self.english["TelegramPremium"])
        self.assertEqual("Chat Business", self.english["TelegramBusiness"])

    def test_shipped_string_values_have_no_telegram_brand_or_owned_links(self):
        standalone_resources = ROOT / "TMessagesProj_AppStandalone/src/main/res/values/strings.xml"
        resource_files = sorted(RES.glob("values*/strings.xml")) + [standalone_resources]
        self.assertTrue(resource_files, "expected shipped Android string resources")

        for path in resource_files:
            root = ET.parse(path).getroot()
            for item in root.findall("string"):
                value = "".join(item.itertext())
                with self.subTest(locale=path.parent.name, key=item.get("name")):
                    self.assertIsNone(TELEGRAM_NAME.search(value), value)
                    self.assertEqual([], list(telegram_owned_targets(value)), value)

    def test_android_brand_surfaces_use_chat_resources_with_simplified_chinese_copy(self):
        passcode = (ROOT / "TMessagesProj/src/main/java/org/telegram/ui/Components/PasscodeView.java").read_text(encoding="utf-8")
        self.assertRegex(
            passcode,
            r'title\.setTypeface\(AndroidUtilities\.bold\(\)\);\s*'
            r'title\.setText\(LocaleController\.getString\(R\.string\.UnlockToUse\)\);',
        )

        new_contact = (ROOT / "TMessagesProj/src/main/java/org/telegram/ui/NewContactBottomSheet.java").read_text(encoding="utf-8")
        self.assertIn(
            "replaceSingleTag(LocaleController.getString(R.string.PhoneNumberNotOnChatWithInvite),",
            new_contact,
        )
        self.assertIn(
            "underPhoneTextView.setText(LocaleController.getString(R.string.PhoneNumberOnChat));",
            new_contact,
        )
        self.assertTrue(
            re.search(
                r'intent\.putExtra\("sms_body", LocaleController\.getString\(R\.string\.InviteTextWithoutLink\)\);',
                new_contact,
            ),
            "SMS invites should use the localized Chat copy without an unknown download URL",
        )
        self.assertNotIn("telegram.org/dl", new_contact)

        contacts = (ROOT / "TMessagesProj/src/main/java/org/telegram/messenger/ContactsController.java").read_text(encoding="utf-8")
        for key in ("ChatProfile", "VoiceCallViaTelegram", "VideoCallViaTelegram"):
            with self.subTest(contact_label=key):
                self.assertIn(
                    f"ContactsContract.Data.DATA2, LocaleController.getString(R.string.{key})",
                    contacts,
                )

        document_picker = (ROOT / "TMessagesProj/src/main/java/org/telegram/ui/Components/ChatAttachAlertDocumentLayout.java").read_text(encoding="utf-8")
        self.assertIn("fs.title = LocaleController.getString(R.string.AppName);", document_picker)

        expected_english = {
            "UnlockToUse": "Unlock to use Chat",
            "PhoneNumberNotOnChatWithInvite": "This phone number is not on Chat. **Invite >**",
            "PhoneNumberOnChat": "This phone number is on Chat.",
            "ChatProfile": "Chat Profile",
            "VoiceCallViaTelegram": "Chat Voice Call",
            "VideoCallViaTelegram": "Chat Video Call",
            "InviteTextWithoutLink": "Hey, I\\'m using Chat to chat. Join me!",
        }
        expected_chinese = {
            "UnlockToUse": "解锁后即可使用 Chat",
            "PhoneNumberNotOnChatWithInvite": "该手机号尚未注册 Chat。**邀请 >**",
            "PhoneNumberOnChat": "该手机号已注册 Chat。",
            "ChatProfile": "Chat 个人资料",
            "VoiceCallViaTelegram": "Chat 语音通话",
            "VideoCallViaTelegram": "Chat 视频通话",
            "InviteTextWithoutLink": "我正在使用 Chat，快来和我聊天吧！",
        }
        for key, value in expected_english.items():
            with self.subTest(locale="en", key=key):
                self.assertEqual(value, self.english.get(key))
        for key, value in expected_chinese.items():
            with self.subTest(locale="zh-CN", key=key):
                self.assertEqual(value, self.chinese.get(key))

    def test_contact_invites_use_localized_copy_when_server_link_is_missing(self):
        contacts = (ROOT / "TMessagesProj/src/main/java/org/telegram/messenger/ContactsController.java").read_text(encoding="utf-8")
        match = re.search(r"public String getInviteText\(int contacts\)\s*\{(?P<body>.*?)\n    \}", contacts, re.S)
        self.assertIsNotNone(match, "ContactsController.getInviteText should remain available")
        body = match.group("body")
        self.assertRegex(body, r"if\s*\(TextUtils\.isEmpty\(inviteLink\)\)")
        self.assertIn("LocaleController.getString(R.string.InviteTextWithoutLink)", body)
        self.assertIn("LocaleController.formatString(R.string.InviteText2, inviteLink)", body)
        self.assertNotIn("telegram.org/dl", body)

    def test_cocoon_footer_uses_chat_feature_link_and_has_simplified_chinese_copy(self):
        footer = self.english["CocoonFooter"]
        self.assertIn(r"Chat\'s feature page", footer)
        self.assertNotRegex(footer, re.compile(r"t\.me|telegram", re.IGNORECASE))
        self.assertEqual("https://privatechat.local/features", self.english["CocoonFooterLink"])
        self.assertIn("CocoonFooter", self.chinese)
        self.assertNotRegex(self.chinese["CocoonFooter"], re.compile(r"t\.me|telegram", re.IGNORECASE))
        self.assertIn("Chat", self.chinese["CocoonFooter"])

    def test_real_empty_chat_and_launcher_surfaces_resolve_to_chat_resources(self):
        empty_cell = (ROOT / "TMessagesProj/src/main/java/org/telegram/ui/Cells/DialogsEmptyCell.java").read_text(encoding="utf-8")
        self.assertRegex(empty_cell, r"titleView\.setText\(LocaleController\.getString\(R\.string\.NoChats\)\)")

        release_manifest = ET.parse(ROOT / "TMessagesProj/config/release/AndroidManifest.xml").getroot()
        application = release_manifest.find("application")
        self.assertIsNotNone(application)
        self.assertEqual("@mipmap/chat_launcher", application.get(ANDROID + "icon"))
        self.assertEqual("@mipmap/chat_launcher_round", application.get(ANDROID + "roundIcon"))
        self.assertEqual("@string/AppName", application.get(ANDROID + "label"))

        main_manifest = ET.parse(ROOT / "TMessagesProj/src/main/AndroidManifest.xml").getroot()
        main_application = main_manifest.find("application")
        launcher_aliases = []
        for alias in main_application.findall("activity-alias"):
            actions = {node.get(ANDROID + "name") for node in alias.findall("intent-filter/action")}
            categories = {node.get(ANDROID + "name") for node in alias.findall("intent-filter/category")}
            if "android.intent.action.MAIN" in actions and "android.intent.category.LAUNCHER" in categories:
                launcher_aliases.append(alias)
        self.assertTrue(launcher_aliases, "launcher aliases must be present")
        default_launcher = next(
            (alias for alias in launcher_aliases if alias.get(ANDROID + "name", "").endswith(".DefaultIcon")),
            None,
        )
        self.assertIsNotNone(default_launcher)
        self.assertEqual("true", default_launcher.get(ANDROID + "enabled"))

        icon = ET.parse(RES / "mipmap-anydpi-v26/chat_launcher.xml").getroot()
        self.assertEqual("@drawable/chat_logo", icon.find("foreground").get(ANDROID + "drawable"))
        self.assertEqual("@drawable/chat_icon_background", icon.find("background").get(ANDROID + "drawable"))
        self.assertEqual("@drawable/chat_logo_monochrome", icon.find("monochrome").get(ANDROID + "drawable"))
        self.assertTrue((RES / "drawable/chat_logo.xml").is_file())
        self.assertTrue((RES / "mipmap-anydpi-v26/chat_launcher_round.xml").is_file())

    def test_android_configuration_validator_accepts_chat_brand_and_localization(self):
        verifier = ROOT / "scripts/verify_private_chat_android_config.py"
        result = subprocess.run(
            [sys.executable, str(verifier)], cwd=ROOT, text=True, capture_output=True
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_first_language_choice_keeps_a_supported_saved_language_and_defaults_to_chinese(self):
        tools = jdk_tools()
        self.assertIsNotNone(tools, "a JDK is required to execute the real language-selection policy")
        javac, java = tools
        selector = ROOT / "TMessagesProj/src/main/java/org/telegram/messenger/InitialLocaleSelector.java"
        with tempfile.TemporaryDirectory(prefix="chat-locale-test-") as directory:
            temp = Path(directory)
            harness = temp / "InitialLocaleSelectorTest.java"
            harness.write_text(
                "import org.telegram.messenger.InitialLocaleSelector;\n"
                "public class InitialLocaleSelectorTest {\n"
                "  public static void main(String[] args) {\n"
                "    check(\"zh_cn\", InitialLocaleSelector.select(null, false));\n"
                "    check(\"en\", InitialLocaleSelector.select(\"en\", true));\n"
                "    check(\"pt_br\", InitialLocaleSelector.select(\"pt_br\", true));\n"
                "    check(\"zh_cn\", InitialLocaleSelector.select(\"missing\", false));\n"
                "  }\n"
                "  private static void check(String expected, String actual) {\n"
                "    if (!expected.equals(actual)) throw new AssertionError(expected + \" != \" + actual);\n"
                "  }\n"
                "}\n",
                encoding="utf-8",
            )
            compiled = subprocess.run(
                [javac, "-d", str(temp), str(selector), str(harness)], text=True, capture_output=True
            )
            self.assertEqual(0, compiled.returncode, compiled.stdout + compiled.stderr)
            result = subprocess.run(
                [java, "-cp", str(temp), "InitialLocaleSelectorTest"], text=True, capture_output=True
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_launcher_manifests_use_chat_assets_and_intro_does_not_render_telegram_art(self):
        manifests = list((ROOT / "TMessagesProj").rglob("AndroidManifest*.xml"))
        self.assertTrue(manifests)
        for path in manifests:
            if re.search(r'@mipmap/ic_launcher(?:_round)?["\s]', path.read_text(encoding="utf-8")):
                self.fail(f"launcher manifest still uses Telegram artwork: {path.relative_to(ROOT)}")
        intro = (ROOT / "TMessagesProj/src/main/java/org/telegram/ui/IntroActivity.java").read_text(encoding="utf-8")
        self.assertNotIn("R.drawable.telegram_logo", intro)
        self.assertNotIn("R.drawable.intro_tg_plane", intro)
        self.assertTrue((RES / "mipmap-anydpi-v26/chat_launcher.xml").is_file())
        self.assertTrue((RES / "drawable/chat_logo.xml").is_file())
        for launcher in ("mipmap-anydpi-v26/ic_launcher.xml", "mipmap-anydpi-v26/ic_launcher_round.xml"):
            contents = (RES / launcher).read_text(encoding="utf-8")
            with self.subTest(launcher=launcher):
                self.assertIn("@drawable/chat_logo_monochrome", contents)
                self.assertNotIn("@drawable/icon_plane", contents)
        self.assertFalse((RES / "drawable/icon_plane.xml").exists())

    def test_account_contacts_and_call_surfaces_use_chat_assets(self):
        auth = (RES / "xml/auth.xml").read_text(encoding="utf-8")
        contacts = (RES / "xml/contacts.xml").read_text(encoding="utf-8")
        notifications = (ROOT / "TMessagesProj/src/main/java/org/telegram/messenger/NotificationsController.java").read_text(encoding="utf-8")
        voip = (ROOT / "TMessagesProj/src/main/java/org/telegram/messenger/voip/VoIPService.java").read_text(encoding="utf-8")

        for path, contents in (
            ("auth.xml", auth),
            ("contacts.xml", contacts),
            ("NotificationsController.java", notifications),
            ("VoIPService.java", voip),
        ):
            with self.subTest(path=path):
                self.assertNotIn("ic_launcher_dr", contents)

        self.assertIn('android:icon="@drawable/chat_logo"', auth)
        self.assertIn('android:smallIcon="@drawable/chat_logo_monochrome"', auth)
        self.assertEqual(3, contacts.count('android:icon="@drawable/chat_logo"'))
        self.assertIn("R.drawable.chat_logo", notifications)
        self.assertIn("R.drawable.chat_logo", voip)

    def test_qr_and_round_video_branding_use_chat_mark(self):
        qr_sources = (
            "TMessagesProj/src/main/java/org/telegram/ui/CallLogActivity.java",
            "TMessagesProj/src/main/java/org/telegram/ui/FilterChatlistActivity.java",
            "TMessagesProj/src/main/java/org/telegram/ui/FilterCreateActivity.java",
            "TMessagesProj/src/main/java/org/telegram/ui/QrActivity.java",
            "TMessagesProj/src/main/java/org/telegram/ui/Components/BlockingUpdateView.java",
            "TMessagesProj/src/main/java/org/telegram/ui/Components/LinkActionView.java",
        )
        for relative_path in qr_sources:
            contents = (ROOT / relative_path).read_text(encoding="utf-8")
            with self.subTest(path=relative_path):
                self.assertIn("R.drawable.chat_logo", contents)
                self.assertNotRegex(contents, r"R\.raw\.qr_code_logo(?:_2)?")

        video_overlay = (
            ROOT / "TMessagesProj/src/main/java/org/telegram/ui/Components/InstantCameraVideoEncoderOverlayHelper.java"
        ).read_text(encoding="utf-8")
        self.assertIn("R.drawable.chat_logo", video_overlay)
        self.assertNotIn("R.raw.plane_logo_plain", video_overlay)

        legacy_assets = (
            "raw/qr_code_logo.json",
            "raw/qr_code_logo_2.json",
            "raw/plane_logo_plain.json",
            "drawable/telegram_logo.xml",
            "drawable/telegram_logo_2.xml",
            "drawable-mdpi/intro_tg_plane.webp",
            "drawable-hdpi/intro_tg_plane.webp",
            "drawable-xhdpi/intro_tg_plane.webp",
            "drawable-xxhdpi/intro_tg_plane.webp",
        )
        for relative_path in legacy_assets:
            with self.subTest(asset=relative_path):
                self.assertFalse((RES / relative_path).exists())

    def test_launcher_aliases_keep_chat_variant_assets(self):
        expected = {
            "VintageIcon": ("@mipmap/chat_launcher_vintage", "@mipmap/chat_launcher_vintage"),
            "AquaIcon": ("@mipmap/chat_launcher_aqua", "@mipmap/chat_launcher_aqua"),
            "PremiumIcon": ("@mipmap/chat_launcher_premium", "@mipmap/chat_launcher_premium"),
            "TurboIcon": ("@mipmap/chat_launcher_turbo", "@mipmap/chat_launcher_turbo"),
            "NoxIcon": ("@mipmap/chat_launcher_nox", "@mipmap/chat_launcher_nox"),
        }

        def aliases(path):
            root = ET.parse(path).getroot()
            return {
                alias.get(ANDROID + "name").rsplit(".", 1)[-1]: (
                    alias.get(ANDROID + "icon"), alias.get(ANDROID + "roundIcon")
                )
                for alias in root.findall("application/activity-alias")
                if alias.get(ANDROID + "name", "").rsplit(".", 1)[-1] in expected
            }

        self.assertEqual(expected, aliases(ROOT / "TMessagesProj/src/main/AndroidManifest.xml"))
        self.assertEqual(expected, aliases(ROOT / "TMessagesProj/config/release/AndroidManifest_standalone.xml"))

        for resource in expected.values():
            for name in resource:
                self.assertTrue((RES / "mipmap-anydpi" / (name.rsplit("/", 1)[-1] + ".xml")).is_file())
                self.assertTrue((RES / "mipmap-anydpi-v26" / (name.rsplit("/", 1)[-1] + ".xml")).is_file())


if __name__ == "__main__":
    unittest.main()
