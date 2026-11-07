import json
import plistlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from scripts.verify_private_chat_ios_config import parse_strings_file


ROOT = Path(__file__).resolve().parents[2]
IOS_APP = ROOT / "Telegram/Telegram-iOS"


def parse_xcconfig(path):
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("//") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def read_png_pixels(path):
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"not a PNG file: {path}")

    chunks = []
    offset = 8
    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        chunks.append((kind, payload))
        offset += length + 12

    header = next(payload for kind, payload in chunks if kind == b"IHDR")
    width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
        ">IIBBBBB", header
    )
    if bit_depth != 8 or color_type not in (2, 6) or compression or filter_method or interlace:
        raise AssertionError(f"unsupported app icon PNG encoding: {path}")

    bytes_per_pixel = 4 if color_type == 6 else 3
    stride = width * bytes_per_pixel
    raw = zlib.decompress(b"".join(payload for kind, payload in chunks if kind == b"IDAT"))
    rows = []
    prior = bytearray(stride)
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        source = raw[cursor + 1 : cursor + 1 + stride]
        cursor += stride + 1
        row = bytearray(stride)
        for index, value in enumerate(source):
            left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            up = prior[index]
            upper_left = prior[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            if filter_type == 1:
                value += left
            elif filter_type == 2:
                value += up
            elif filter_type == 3:
                value += (left + up) // 2
            elif filter_type == 4:
                base = left + up - upper_left
                distances = (abs(base - left), abs(base - up), abs(base - upper_left))
                predictor = (left, up, upper_left)[distances.index(min(distances))]
                value += predictor
            elif filter_type != 0:
                raise AssertionError(f"unsupported PNG filter {filter_type}: {path}")
            row[index] = value & 0xFF
        rows.append(row)
        prior = row

    def pixel(x, y):
        start = x * bytes_per_pixel
        return tuple(rows[y][start : start + bytes_per_pixel])

    return width, height, pixel


class ChatAppBrandingTests(unittest.TestCase):
    def test_app_declares_a_single_scene_configuration_for_its_scene_delegate(self):
        import plistlib

        info = plistlib.loads((IOS_APP / "Info.plist").read_bytes())
        manifest = info.get("UIApplicationSceneManifest")
        self.assertIsInstance(manifest, dict)
        self.assertFalse(manifest.get("UIApplicationSupportsMultipleScenes", True))

        configurations = manifest.get("UISceneConfigurations", {})
        app_configurations = configurations.get("UIWindowSceneSessionRoleApplication", [])
        self.assertEqual(1, len(app_configurations))
        self.assertEqual("Chat Application Scene", app_configurations[0].get("UISceneConfigurationName"))
        self.assertEqual("AppSceneDelegate", app_configurations[0].get("UISceneDelegateClassName"))

        build = (ROOT / "Telegram/BUILD").read_text(encoding="utf-8")
        main_plist = build.split('name = "TelegramInfoPlist"', 1)[1].split("plist_fragment(", 1)[0]
        self.assertIn("<key>UIApplicationSceneManifest</key>", main_plist)
        self.assertIn("<key>UISceneDelegateClassName</key>", main_plist)
        self.assertIn("<string>AppSceneDelegate</string>", main_plist)

        app_delegate = (
            ROOT / "submodules/TelegramUI/Sources/AppDelegate.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("@objc(AppSceneDelegate)", app_delegate)
        self.assertIn("func scene(_ scene: UIScene, willConnectTo", app_delegate)
        scene_delegate = app_delegate.split("@objc(AppSceneDelegate)", 1)[1]
        self.assertRegex(
            scene_delegate,
            r"if let shortcutItem = connectionOptions\.shortcutItem\s*\{\s*"
            r"appDelegate\.application\(UIApplication\.shared,\s*"
            r"performActionFor: shortcutItem,\s*completionHandler:",
        )

    def test_keyboard_window_lookup_uses_the_app_window_scene(self):
        app_delegate = (
            ROOT / "submodules/TelegramUI/Sources/AppDelegate.swift"
        ).read_text(encoding="utf-8")
        keyboard_window = re.search(
            r"var keyboardWindow: UIWindow\? \{(.*?)\n    \}\n    \n    var keyboardView",
            app_delegate,
            re.S,
        )
        self.assertIsNotNone(keyboard_window)
        source = keyboard_window.group(1)
        self.assertNotIn("internalGetKeyboard", source)
        self.assertIn("guard let scene = self.scene", source)
        self.assertRegex(
            source,
            r"for window in scene\.windows\s*\{\s*"
            r"if isKeyboardWindow\(window: window\)",
        )

    def test_camera_orientation_uses_the_view_window_scene(self):
        source = (
            ROOT / "submodules/Camera/Sources/CameraPreviewView.swift"
        ).read_text(encoding="utf-8")

        self.assertIn("self.window?.windowScene?.interfaceOrientation", source)
        self.assertNotIn("UIApplication.shared.windows", source)

    def test_pasteboard_text_types_use_uniform_type_identifiers(self):
        pasteboard = (
            ROOT / "submodules/Pasteboard/Sources/Pasteboard.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("UTType.utf8PlainText.identifier", pasteboard)
        self.assertIn("UTType.rtf.identifier", pasteboard)
        self.assertNotRegex(pasteboard, r"\bkUTType(?:UTF8PlainText|RTF)\b")

    def test_ios_deployment_minimum_matches_the_current_xcode_platform_floor(self):
        build = (ROOT / "Telegram/BUILD").read_text(encoding="utf-8")
        minimum = re.search(r'^minimum_os_version = "([0-9.]+)"$', build, re.M)
        self.assertIsNotNone(minimum)
        self.assertGreaterEqual(tuple(map(int, minimum.group(1).split("."))), (15, 0))

        project_generator = (
            ROOT / "build-system/MakeProject/Sources/MakeProject/ProjectGenerator.swift"
        ).read_text(encoding="utf-8")
        self.assertIn('"IPHONEOS_DEPLOYMENT_TARGET": "15.0"', project_generator)

    def test_built_app_name_is_chat(self):
        config = parse_xcconfig(IOS_APP / "Config-Fork.xcconfig")
        self.assertEqual("Chat", config["APP_NAME"])

        build_text = (ROOT / "Telegram/BUILD").read_text(encoding="utf-8")
        display_name_fragments = re.findall(
            r'<key>CFBundleDisplayName</key>\s*<string>([^<]+)</string>',
            build_text,
        )
        self.assertTrue(display_name_fragments)
        self.assertEqual({"Chat"}, set(display_name_fragments))

        localized_names = []
        for path in IOS_APP.glob("*.lproj/InfoPlist.strings"):
            localized_names.extend(
                re.findall(
                    r'"CFBundleDisplayName"\s*=\s*"([^"\\]*(?:\\.[^"\\]*)*)";',
                    path.read_text(encoding="utf-8"),
                )
            )
        self.assertEqual(["Chat"] * len(localized_names), localized_names)

    def test_siri_intent_vocabulary_uses_chat_branding_in_every_locale(self):
        import plistlib

        vocabulary_files = sorted(IOS_APP.glob("*.lproj/AppIntentVocabulary.plist"))
        self.assertTrue(vocabulary_files)
        for path in vocabulary_files:
            vocabulary = plistlib.loads(path.read_bytes())
            examples = [
                example
                for phrase in vocabulary["IntentPhrases"]
                for example in phrase["IntentExamples"]
            ]
            with self.subTest(language=path.parent.name):
                self.assertTrue(examples)
                self.assertTrue(all("Chat" in example for example in examples))
                self.assertFalse(any("Telegram" in example for example in examples))

        chinese_vocabulary = IOS_APP / "zh-Hans.lproj/AppIntentVocabulary.plist"
        self.assertTrue(chinese_vocabulary.is_file())

    def test_appstore_llc_configuration_uses_chat_release_identity(self):
        config = parse_xcconfig(IOS_APP / "Config-AppStoreLLC.xcconfig")
        fork = parse_xcconfig(IOS_APP / "Config-Fork.xcconfig")

        self.assertEqual("Chat", config["APP_NAME"])
        self.assertEqual("com.privatechat.ios", config["APP_BUNDLE_ID"])
        self.assertEqual("privatechat", config["APP_SPECIFIC_URL_SCHEME"])
        self.assertEqual(fork["GLOBAL_CONSTANTS"], config["GLOBAL_CONSTANTS"])
        self.assertEqual(
            fork["GCC_PREPROCESSOR_DEFINITIONS"],
            config["GCC_PREPROCESSOR_DEFINITIONS"],
        )

    def test_active_app_icon_uses_chat_artwork(self):
        icon = json.loads((IOS_APP / "Telegram.icon/icon.json").read_text(encoding="utf-8"))
        icon_assets = IOS_APP / "Telegram.icon/Assets"
        image_names = {
            layer["image-name"]
            for group in icon["groups"]
            for layer in group["layers"]
        }
        self.assertIn("Chat.svg", image_names)
        self.assertTrue((icon_assets / "Chat.svg").is_file())
        self.assertIn("ChatBackground.svg", image_names)
        self.assertTrue((icon_assets / "ChatBackground.svg").is_file())
        self.assertNotIn("Plane.svg", image_names)
        self.assertNotIn("Oval.svg", image_names)

        background = (icon_assets / "ChatBackground.svg").read_text(encoding="utf-8")
        self.assertIn("#145B57", background.upper())

        serialized = json.dumps(icon)
        self.assertNotIn("0.21569,0.68627,0.89020", serialized)
        self.assertIn("0.07843,0.35686,0.34118", serialized)

    def test_embedded_watch_app_uses_chat_identity_and_artwork(self):
        watch_root = ROOT / "Telegram/WatchApp/tgwatch Watch App"
        info = plistlib.loads((watch_root / "Info.plist").read_bytes())
        self.assertEqual("Chat", info["CFBundleDisplayName"])

        project = (ROOT / "Telegram/WatchApp/project.yml").read_text(encoding="utf-8")
        self.assertRegex(project, r"(?m)^  developmentLanguage: zh-Hans$")
        self.assertRegex(project, r"(?m)^        CFBundleDisplayName: Chat$")

        generated_project = (
            ROOT / "Telegram/WatchApp/tgwatch.xcodeproj/project.pbxproj"
        ).read_text(encoding="utf-8")
        self.assertIn('developmentRegion = "zh-Hans";', generated_project)
        self.assertIn("WatchCopy.swift in Sources", generated_project)
        self.assertIn("Localizable.strings in Resources", generated_project)
        self.assertIn("InfoPlist.strings in Resources", generated_project)

        watch_icon = watch_root / "Assets.xcassets/AppIcon.appiconset/AppIcon.png"
        chat_icon = IOS_APP / "DefaultAppIcon.xcassets/AppIconLLC.appiconset/Simple-iTunesArtwork.png"
        self.assertEqual(chat_icon.read_bytes(), watch_icon.read_bytes())

        for language in ("en", "zh-Hans"):
            localized_info = parse_strings_file(
                (watch_root / f"{language}.lproj/InfoPlist.strings").read_text(encoding="utf-8")
            )
            self.assertEqual("Chat", localized_info["CFBundleDisplayName"])

    def test_watch_qr_login_screen_has_english_and_simplified_chinese_copy(self):
        watch_root = ROOT / "Telegram/WatchApp/tgwatch Watch App"
        auth_sources = {
            "content": (watch_root / "ContentView.swift").read_text(encoding="utf-8"),
            "qr": (watch_root / "Auth/QrLoginView.swift").read_text(encoding="utf-8"),
            "password": (watch_root / "Auth/PasswordEntryView.swift").read_text(encoding="utf-8"),
            "error": (watch_root / "Auth/ErrorView.swift").read_text(encoding="utf-8"),
            "closed": (watch_root / "Auth/ClosedView.swift").read_text(encoding="utf-8"),
            "auth_mapping": (watch_root / "AuthStateMapping.swift").read_text(encoding="utf-8"),
            "error_mapping": (watch_root / "ErrorMapping.swift").read_text(encoding="utf-8"),
            "bootstrap": (watch_root / "Accounts/AccountBootstrapView.swift").read_text(encoding="utf-8"),
            "account_manager": (watch_root / "Accounts/AccountManager.swift").read_text(encoding="utf-8"),
        }
        required = {
            "watch.state.starting": ("Starting…", "正在启动…"),
            "watch.state.configuring": ("Configuring…", "正在配置…"),
            "watch.state.preparingQR": ("Preparing QR…", "正在准备二维码…"),
            "watch.state.loading": ("Loading…", "正在加载…"),
            "watch.state.loggingOut": ("Logging out…", "正在退出登录…"),
            "watch.state.preparing": ("Preparing…", "正在准备…"),
            "watch.auth.unexpectedSMS": (
                "Unexpected SMS-code prompt during QR login.",
                "二维码登录期间出现了非预期的短信验证码步骤。",
            ),
            "watch.login.qr.title": ("Log in to Chat by QR Code", "通过二维码登录 Chat"),
            "watch.login.qr.phoneSettings": ("Settings on your Phone", "手机上的设置"),
            "watch.login.qr.devices": ("Devices", "设备"),
            "watch.login.qr.scan": ("Scan QR", "扫描二维码"),
            "watch.login.qr.renderError": ("Could not render QR code", "无法生成二维码"),
            "watch.environment.test": ("TEST", "测试"),
            "watch.login.password.hint": ("Hint: %@", "提示：%@"),
            "watch.login.password.prompt": ("Enter your cloud password", "请输入两步验证密码"),
            "watch.login.password.field": ("Password", "两步验证密码"),
            "watch.login.password.continue": ("Continue", "继续"),
            "watch.login.password.title": ("Password", "两步验证"),
            "watch.action.ok": ("OK", "确定"),
            "watch.action.tryAgain": ("Try again", "重试"),
            "watch.error.title": ("Something went wrong", "出现了问题"),
            "watch.error.accountPersist": (
                "Couldn't save account list.",
                "无法保存账号列表。",
            ),
            "watch.session.loggedOut": ("Logged out", "已退出登录"),
            "watch.session.relaunch": (
                "Relaunch the app to sign in again.",
                "请重新启动 Chat 以再次登录。",
            ),
            "watch.auth.emailUnsupported": (
                "Email-based login isn't supported in this build yet.",
                "此版本暂不支持通过电子邮件登录。",
            ),
            "watch.auth.registrationUnsupported": (
                "Registration is not supported with QR login.",
                "二维码登录暂不支持注册新账号。",
            ),
            "watch.auth.premiumUnsupported": (
                "Premium-purchase login isn't supported in this build yet.",
                "此版本暂不支持通过购买高级版登录。",
            ),
            "watch.auth.stateUnsupported": (
                "Unsupported authorization state.",
                "暂不支持此授权状态。",
            ),
            "watch.auth.type.appMessage": ("In-app message", "应用内消息"),
            "watch.auth.type.phoneCall": ("Phone call", "电话"),
            "watch.auth.type.missedCall": ("Missed call", "未接来电"),
            "watch.auth.type.flashCall": ("Flash call", "闪呼"),
            "watch.auth.type.fragment": ("Fragment", "Fragment"),
            "watch.auth.type.appPush": ("App push", "应用推送"),
            "watch.auth.type.code": ("Code", "验证码"),
            "watch.error.unknown": ("An error occurred", "发生错误"),
            "watch.error.incorrectPassword": ("Incorrect password", "密码错误"),
            "watch.error.phoneInvalid": (
                "That phone number doesn't look right.",
                "手机号格式不正确。",
            ),
            "watch.error.codeInvalid": ("That code is wrong.", "验证码错误。"),
            "watch.error.codeExpired": (
                "Code expired — request a new one.",
                "验证码已过期，请重新获取。",
            ),
            "watch.error.firstNameInvalid": (
                "That first name doesn't look right.",
                "名字格式不正确。",
            ),
            "watch.error.lastNameInvalid": (
                "That last name doesn't look right.",
                "姓氏格式不正确。",
            ),
            "watch.error.floodWait": (
                "Too many attempts. Wait %ds.",
                "尝试次数过多，请等待 %d 秒。",
            ),
            "watch.error.floodWaitLater": (
                "Too many attempts. Try again later.",
                "尝试次数过多，请稍后重试。",
            ),
        }

        source_keys = {
            "content": (
                "watch.state.starting",
                "watch.state.configuring",
                "watch.state.preparingQR",
                "watch.auth.unexpectedSMS",
                "watch.state.loading",
                "watch.state.loggingOut",
            ),
            "qr": (
                "watch.login.qr.title",
                "watch.environment.test",
                "watch.login.qr.phoneSettings",
                "watch.login.qr.devices",
                "watch.login.qr.scan",
                "watch.login.qr.renderError",
            ),
            "password": (
                "watch.login.password.hint",
                "watch.login.password.prompt",
                "watch.login.password.field",
                "watch.login.password.continue",
                "watch.login.password.title",
                "watch.action.ok",
            ),
            "error": ("watch.error.title", "watch.environment.test"),
            "closed": ("watch.session.loggedOut", "watch.session.relaunch"),
            "auth_mapping": tuple(
                key
                for key in required
                if key.startswith("watch.auth.") and key != "watch.auth.unexpectedSMS"
            ),
            "error_mapping": tuple(
                key
                for key in required
                if key.startswith("watch.error.")
                and key not in ("watch.error.title", "watch.error.accountPersist")
            ),
            "bootstrap": ("watch.action.tryAgain", "watch.state.preparing"),
            "account_manager": ("watch.error.accountPersist",),
        }
        for name, keys in source_keys.items():
            source = auth_sources[name]
            for key in keys:
                if key == "watch.login.password.hint":
                    self.assertIn('WatchCopy.format("watch.login.password.hint"', source)
                else:
                    self.assertIn(f'"{key}"', source)

        english = parse_strings_file(
            (watch_root / "en.lproj/Localizable.strings").read_text(encoding="utf-8")
        )
        chinese = parse_strings_file(
            (watch_root / "zh-Hans.lproj/Localizable.strings").read_text(encoding="utf-8")
        )
        for key, (english_value, chinese_value) in required.items():
            with self.subTest(key=key):
                self.assertEqual(english_value, english.get(key))
                self.assertEqual(chinese_value, chinese.get(key))

    def test_shipped_ios_app_icon_assets_use_the_chat_mark(self):
        icon_set = IOS_APP / "DefaultAppIcon.xcassets/AppIconLLC.appiconset"
        manifest = json.loads((icon_set / "Contents.json").read_text(encoding="utf-8"))
        images = [item for item in manifest["images"] if "filename" in item]
        filenames = {item["filename"] for item in images}
        self.assertTrue(
            {
                "BlueIcon@2x.png",
                "BlueIcon@3x.png",
                "BlueIconIpad@2x.png",
                "BlueIconLargeIpad@2x.png",
                "Simple-iTunesArtwork.png",
            }.issubset(filenames)
        )

        for item in images:
            path = icon_set / item["filename"]
            width, height, pixel = read_png_pixels(path)
            size = float(item["size"].split("x")[0])
            scale = int(item["scale"].removesuffix("x"))
            expected = round(size * scale)
            corner = pixel(0, 0)
            center = pixel(width // 2, height // 2)
            orange = pixel(round(width * 780 / 1024), round(height * 350 / 1024))
            with self.subTest(filename=item["filename"]):
                self.assertEqual((expected, expected), (width, height))
                self.assertEqual((20, 91, 87), corner[:3])
                if len(corner) == 4:
                    self.assertEqual(255, corner[3])
                self.assertGreaterEqual(min(center[:3]), 200)
                self.assertGreater(orange[0], 220)
                self.assertGreater(orange[1], 120)
                self.assertLess(orange[2], 150)

        artwork = icon_set / "Simple-iTunesArtwork.png"
        width, height, pixel = read_png_pixels(artwork)
        self.assertEqual((1024, 1024), (width, height))
        self.assertEqual((255, 255, 255), pixel(512, 512)[:3])

    def test_initial_localization_defaults_to_chinese_and_preserves_existing(self):
        helper = ROOT / "submodules/AuthorizationUI/Sources/InitialLocalization.swift"
        self.assertTrue(helper.is_file(), "the startup language policy must be shared and testable")

        compiler = shutil.which("swiftc")
        if compiler is None:
            self.skipTest("swiftc is unavailable")

        harness = """
import Foundation
print(InitialLocalization.code(for: [\"zh-Hans-CN\", \"en-US\"]))
print(InitialLocalization.code(for: [\"zh-Hant-TW\"]))
print(InitialLocalization.code(for: [\"en-US\", \"zh-CN\"]))
print(InitialLocalization.code(for: []))
print(InitialLocalization.introResourceCode(for: "zh-hans"))
print(InitialLocalization.introResourceCode(for: "zh-Hant-TW"))
print(InitialLocalization.startButtonTitle(for: "en"))
print(InitialLocalization.startButtonTitle(for: "zh-hans"))
print(InitialLocalization.startButtonTitle(for: "zh-hant"))
print(InitialLocalization.code(for: [\"zh-CN\"], existingLanguageCode: \"en\"))
print(InitialLocalization.code(for: [\"en-US\"], existingLanguageCode: \"fr\"))
print(InitialLocalization.shouldUseBundledStrings(languageCode: \"zh-hans\", existingLanguageCode: nil))
print(InitialLocalization.shouldUseBundledStrings(languageCode: \"zh-Hans\", existingLanguageCode: \"en\"))
print(InitialLocalization.shouldUseBundledStrings(languageCode: \"zh-hant\", existingLanguageCode: nil))
print(InitialLocalization.shouldUseBundledStrings(languageCode: \"en\", existingLanguageCode: nil))
"""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "main.swift"
            binary = Path(directory) / "initial-localization"
            source.write_text(harness, encoding="utf-8")
            subprocess.run(
                [compiler, str(helper), str(source), "-o", str(binary)],
                check=True,
                capture_output=True,
                text=True,
            )
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
        self.assertEqual(
            "zh-hans\nzh-hant\nzh-hans\nzh-hans\nzh-Hans\nzh-Hant\nStart Messaging\n开始聊天\n開始聊天\nen\nfr\ntrue\nfalse\nfalse\nfalse\n",
            result.stdout,
        )

    def test_default_presentation_strings_use_bundled_simplified_chinese_with_english_fallback(self):
        default_strings = (
            ROOT / "submodules/TelegramPresentationData/Sources/DefaultPresentationStrings.swift"
        ).read_text(encoding="utf-8")
        self.assertIn('languageCode: "zh-hans"', default_strings)
        self.assertIn('forLocalization: "zh-Hans"', default_strings)

        build = (ROOT / "Telegram/BUILD").read_text(encoding="utf-8")
        self.assertIn('"Telegram-iOS/zh-Hans.lproj/Localizable.strings"', build)

        simplified = parse_strings_file(
            (IOS_APP / "zh-Hans.lproj/Localizable.strings").read_text(encoding="utf-8")
        )
        english = parse_strings_file(
            (IOS_APP / "en.lproj/Localizable.strings").read_text(encoding="utf-8")
        )
        self.assertEqual("你的手机号", simplified["Login.PhoneTitle"])
        self.assertEqual("Settings", english["Settings.Title"])

        generator = (ROOT / "build-system/GenerateStrings/GenerateStrings.py").read_text(
            encoding="utf-8"
        )
        single_lookup = generator.split("static NSString * _Nonnull getSingle(", 1)[1].split(
            "static NSString * _Nonnull getSingleIndirect(", 1
        )[0]
        self.assertIn("strings.primaryComponent.dict[key]", single_lookup)
        self.assertIn("fallbackDict[key]", single_lookup)

        if sys.platform != "darwin":
            return

        swift = shutil.which("swiftc")
        clang = shutil.which("clang")
        if swift is None or clang is None:
            self.skipTest("Swift and Clang are required for the strings runtime harness")

        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            bundle = work / "Localization.bundle"
            bundle.mkdir()
            (bundle / "Info.plist").write_text(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<plist version="1.0"><dict><key>CFBundleIdentifier</key>'
                '<string>chat.localization.tests</string></dict></plist>',
                encoding="utf-8",
            )
            for language in ("en", "zh-Hans"):
                destination = bundle / f"{language}.lproj"
                destination.mkdir()
                shutil.copyfile(
                    IOS_APP / f"{language}.lproj/Localizable.strings",
                    destination / "Localizable.strings",
                )

            include = work / "include"
            headers = include / "PresentationStrings"
            headers.mkdir(parents=True)
            generated = work / "PresentationStrings.m"
            header = headers / "PresentationStrings.h"
            subprocess.run(
                [
                    "python3", str(ROOT / "build-system/GenerateStrings/GenerateStrings.py"),
                    "--source", str(IOS_APP / "en.lproj/Localizable.strings"),
                    "--outImplementation", str(generated),
                    "--outHeader", str(header),
                    "--outData", str(bundle / "PresentationStrings.data"),
                ],
                check=True, capture_output=True, text=True,
            )
            app_bundle = include / "AppBundle"
            app_bundle.mkdir()
            (app_bundle / "AppBundle.h").write_text(
                '#import <Foundation/Foundation.h>\nNSBundle * _Nonnull getAppBundle(void);\n',
                encoding="utf-8",
            )
            (include / "module.modulemap").write_text(
                'module PresentationStrings { header "PresentationStrings/PresentationStrings.h" export * }\n'
                'module AppBundle { header "AppBundle/AppBundle.h" export * }\n',
                encoding="utf-8",
            )
            bundle_source = work / "AppBundle.m"
            bundle_source.write_text(
                '#import <AppBundle/AppBundle.h>\n'
                f'NSBundle *getAppBundle(void) {{ return [NSBundle bundleWithPath:@"{bundle}"]; }}\n',
                encoding="utf-8",
            )
            pluralization = ROOT / "submodules/NumberPluralizationForm"
            objects = []
            for index, source in enumerate(
                (generated, bundle_source, pluralization / "Sources/NumberPluralizationForm.m")
            ):
                output = work / f"runtime-{index}.o"
                subprocess.run(
                    [clang, "-fobjc-arc", "-fmodules", "-I", str(include),
                     "-I", str(pluralization / "PublicHeaders"), "-c", str(source), "-o", str(output)],
                    check=True, capture_output=True, text=True,
                )
                objects.append(str(output))

            harness = work / "main.swift"
            harness.write_text(
                'import Foundation\n'
                'print(defaultPresentationStrings.primaryComponent.languageCode)\n'
                'print(defaultPresentationStrings.Login_PhoneTitle)\n'
                'var dict = defaultPresentationStrings.primaryComponent.dict\n'
                'dict.removeValue(forKey: "Settings.Title")\n'
                'let strings = PresentationStrings(primaryComponent: PresentationStrings.Component('
                'languageCode: "zh-hans", localizedName: "简体中文", pluralizationRulesCode: nil, '
                'dict: dict), secondaryComponent: nil, groupingSeparator: "")\n'
                'print(strings.Settings_Title)\n',
                encoding="utf-8",
            )
            binary = work / "localization-runtime"
            subprocess.run(
                [swift, "-I", str(include),
                 str(ROOT / "submodules/TelegramPresentationData/Sources/DefaultPresentationStrings.swift"),
                 str(harness), *objects, "-framework", "Foundation", "-o", str(binary)],
                check=True, capture_output=True, text=True,
            )
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            self.assertEqual("zh-hans\n你的手机号\nSettings\n", result.stdout)

    def test_first_simplified_chinese_start_uses_local_strings_without_waiting_for_remote_language(self):
        helper = (
            ROOT / "submodules/AuthorizationUI/Sources/InitialLocalization.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("shouldUseBundledStrings", helper)

        splash = (
            ROOT / "submodules/AuthorizationUI/Sources/AuthorizationSequenceSplashController.swift"
        ).read_text(encoding="utf-8")
        activation = splash.split("private func activateLocalization(", 1)[1].split(
            "private func pressNext(", 1
        )[0]
        local_path = activation.split("shouldUseBundledStrings", 1)[1].split(
            "let suggestedCode", 1
        )[0]
        self.assertIn("pressNext(strings: defaultPresentationStrings)", local_path)
        self.assertIn("return", local_path)

    def test_managed_localization_updates_skip_missing_settings_without_english_requests_or_writes(self):
        source = (
            ROOT
            / "submodules/TelegramCore/Sources/State/ManagedLocalizationUpdatesOperations.swift"
        ).read_text(encoding="utf-8")
        self.assertRegex(
            source,
            r"func getLocalization\(.*?\)\s*->\s*\(.*?\)\?\s*\{",
        )
        self.assertNotIn('return (primary: ("en", 0, [])', source)
        self.assertNotIn(
            'LocalizationComponent(languageCode: "en", localizedName: "English"', source
        )

        synchronize = source.split("private func synchronizeLocalizationUpdates(", 1)[1].split(
            "func tryApplyingLanguageDifference(", 1
        )[0]
        self.assertIn("guard let (primary, secondary) = getLocalization(transaction)", synchronize)
        self.assertIn("return .fail(.done)", synchronize)
        self.assertIn("return .fail(Void())", synchronize)
        self.assertIn("var currentSettings = transaction.getSharedData", synchronize)
        self.assertIn("guard let (primary, _) = getLocalization(transaction)", synchronize)

    def test_startup_continues_when_the_preferred_language_download_fails(self):
        source = (
            ROOT / "submodules/AuthorizationUI/Sources/AuthorizationSequenceSplashController.swift"
        ).read_text(encoding="utf-8")
        activation = source.split(".localization.downloadAndApplyLocalization", 1)[1]
        activation = activation.split("\n            }))", 1)[0]
        error_callback = re.search(
            r"\.start\(error:\s*\{(?P<body>.*?)\},\s*completed:", activation, re.S
        )

        self.assertIsNotNone(error_callback, "localization failures must release the start flow")
        self.assertIn("controller.isEnabled = true", error_callback.group("body"))
        self.assertIn("startButton.alpha = 1.0", error_callback.group("body"))
        self.assertIn("pressNext(strings: nil)", error_callback.group("body"))

    def test_configuration_poll_does_not_schedule_language_updates_without_settings(self):
        source = (
            ROOT / "submodules/TelegramCore/Sources/State/ManagedConfigurationUpdates.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("guard let (primary, secondary) = getLocalization(transaction)", source)
        self.assertRegex(
            source,
            r"guard let \(primary, secondary\) = getLocalization\(transaction\) else \{\s*return \.complete\(\)",
        )

    def test_explicit_english_selection_applies_settings_on_first_launch(self):
        source = (
            ROOT / "submodules/AuthorizationUI/Sources/AuthorizationSequenceSplashController.swift"
        ).read_text(encoding="utf-8")
        self.assertNotIn('(currentCode ?? "en") == code', source)
        self.assertIn("if currentCode == code", source)

    def test_bazel_generated_app_url_schemes_use_private_chat_brand(self):
        import plistlib

        build = (ROOT / "Telegram/BUILD").read_text(encoding="utf-8")
        fragment = re.search(
            r'plist_fragment\(\s*name = "UrlTypesInfoPlist".*?template\s*=\s*"""(.*?)"""\.format\(',
            build,
            re.S,
        )
        self.assertIsNotNone(fragment, "the built app must provide its URL type plist fragment")
        wrapped_fragment = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<plist version="1.0"><dict>'
            + fragment.group(1)
            + "</dict></plist>"
        )
        info = plistlib.loads(wrapped_fragment.encode("utf-8"))
        schemes = [
            scheme
            for item in info["CFBundleURLTypes"]
            for scheme in item["CFBundleURLSchemes"]
        ]
        self.assertIn("privatechat", schemes)
        self.assertNotIn("telegram", schemes)
        self.assertNotIn("tg", schemes)

    def test_chinese_intro_resources_are_bundled(self):
        build = (ROOT / "Telegram/BUILD").read_text(encoding="utf-8")
        self.assertIn('"Telegram-iOS/zh-Hans.lproj/Localizable.strings"', build)
        self.assertIn('"Telegram-iOS/zh-Hant.lproj/Localizable.strings"', build)
        for language, title, button in (
            ("zh-Hans", "Chat", "开始聊天"),
            ("zh-Hant", "Chat", "開始聊天"),
        ):
            contents = (IOS_APP / f"{language}.lproj/Localizable.strings").read_text(encoding="utf-8")
            self.assertIn(f'"Tour.Title1" = "{title}";', contents)
            self.assertIn(f'"Tour.StartButton" = "{button}";', contents)

    def test_supported_localizations_use_chat_as_the_product_name(self):
        for language in ("en", "zh-Hans", "zh-Hant"):
            strings = parse_strings_file(
                (IOS_APP / f"{language}.lproj/Localizable.strings").read_text(encoding="utf-8")
            )
            stale = {key: value for key, value in strings.items() if "Private Chat" in value}
            with self.subTest(language=language):
                self.assertEqual({}, stale, f"{language} still displays the old product name")

    def test_simplified_chinese_covers_the_initial_authentication_flow(self):
        required_keys = {
            "Common.Cancel",
            "Common.Next",
            "Common.OK",
            "Common.Paste",
            "Common.Search",
            "Login.PhoneAndCountryHelp",
            "Login.PhoneNumberConfirmation",
            "Login.PhonePlaceholder",
            "Login.NewNumber",
            "Login.PhoneTitle",
            "Login.SelectCountry",
            "Login.Continue",
            "Login.Edit",
            "Login.Yes",
            "Login.EnterCodeSMSTitle",
            "Login.EnterCodeSMSText",
            "Login.EnterCodeTelegramTitle",
            "Login.EnterCodeTelegramText",
            "Login.CodeExpired",
            "Login.InvalidCodeError",
            "Login.NetworkError",
            "Login.InfoTitle",
            "Login.TermsOfServiceLabel",
            "Login.TermsOfServiceHeader",
            "Login.TermsOfServiceAgree",
            "Login.TermsOfServiceDecline",
            "UserInfo.FirstNamePlaceholder",
            "UserInfo.LastNamePlaceholder",
            "LoginPassword.Title",
            "LoginPassword.InvalidPasswordError",
            "LoginPassword.ResetAccount",
            "TwoStepAuth.EnterPasswordHelp",
            "TwoStepAuth.EnterPasswordForgot",
            "TwoStepAuth.RecoveryTitle",
            "TwoStepAuth.RecoveryCodeHelp",
        }
        english = parse_strings_file(
            (IOS_APP / "en.lproj/Localizable.strings").read_text(encoding="utf-8")
        )
        chinese = parse_strings_file(
            (IOS_APP / "zh-Hans.lproj/Localizable.strings").read_text(encoding="utf-8")
        )

        self.assertEqual(set(), required_keys - english.keys())
        self.assertEqual(
            set(),
            required_keys - chinese.keys(),
            "the Simplified Chinese authentication strings are incomplete",
        )

        placeholder_pattern = re.compile(r"%(?:\d+\$)?(?:@|d|f|s)")
        for key in sorted(required_keys):
            with self.subTest(key=key):
                self.assertTrue(chinese[key].strip())
                self.assertNotEqual(english[key], chinese[key], f"{key} is still untranslated")
                self.assertEqual(
                    sorted(placeholder_pattern.findall(english[key])),
                    sorted(placeholder_pattern.findall(chinese[key])),
                    f"{key} must preserve its formatting placeholders",
                )

    def test_simplified_chinese_covers_the_main_chat_and_settings_shell(self):
        required_keys = {
            "DialogList.Title",
            "Contacts.Title",
            "Calls.TabTitle",
            "Settings.Title",
            "DialogList.SearchLabel",
            "DialogList.SearchLabelCompact",
            "DialogList.NoMessagesTitle",
            "DialogList.NoMessagesText",
            "DialogList.SearchSectionDialogs",
            "DialogList.SearchSectionMessages",
            "DialogList.SearchSectionMessagesIn",
            "DialogList.SearchSectionRecent",
            "DialogList.SavedMessages",
            "DialogList.SavedMessagesHelp",
            "DialogList.You",
            "DialogList.Draft",
            "ChatList.EmptyChatList",
            "ChatList.EmptyChatListWithArchive",
            "ChatList.EmptyChatListFilterTitle",
            "ChatList.EmptyChatListFilterText",
            "ChatList.EmptyChatListNewMessage",
            "ChatList.EmptyChatListEditFilter",
            "ChatList.Tabs.AllChats",
            "ChatList.Tabs.All",
            "Compose.NewMessage",
            "Settings.Search",
            "Settings.MyProfile",
            "Settings.SetProfilePhotoOrVideo",
            "Settings.Logout",
            "Settings.PhoneNumber",
            "Settings.Username",
            "Settings.PrivacySettings",
            "Settings.NotificationsAndSounds",
            "Settings.ChatSettings",
            "Settings.Appearance",
            "Settings.Devices",
            "Settings.AppLanguage",
            "Settings.CallSettings",
            "Settings.Support",
            "Settings.ChatFolders",
            "Settings.AddAccount",
            "Settings.AddAnotherAccount",
        }
        english = parse_strings_file(
            (IOS_APP / "en.lproj/Localizable.strings").read_text(encoding="utf-8")
        )
        chinese = parse_strings_file(
            (IOS_APP / "zh-Hans.lproj/Localizable.strings").read_text(encoding="utf-8")
        )

        self.assertEqual(set(), required_keys - english.keys())
        self.assertEqual(
            set(),
            required_keys - chinese.keys(),
            "the Simplified Chinese chat and settings strings are incomplete",
        )

        placeholder_pattern = re.compile(r"%(?:\d+\$)?(?:@|d|f|s)")
        for key in sorted(required_keys):
            with self.subTest(key=key):
                self.assertTrue(chinese[key].strip())
                self.assertNotEqual(english[key], chinese[key], f"{key} is still untranslated")
                self.assertEqual(
                    sorted(placeholder_pattern.findall(english[key])),
                    sorted(placeholder_pattern.findall(chinese[key])),
                    f"{key} must preserve its formatting placeholders",
                )

    def test_simplified_chinese_covers_the_core_conversation_flow(self):
        required_keys = {
            "Chat.AttachmentLimitReached",
            "Chat.AttachmentMultipleFilesDisabled",
            "Chat.AttachmentMultipleForwardDisabled",
            "Chat.DeleteMessagesConfirmation_1",
            "Chat.DeleteMessagesConfirmation_any",
            "Chat.MultipleTextMessagesDisabled",
            "Chat.SlowmodeAttachmentLimitReached",
            "Chat.SlowmodeSendError",
            "Chat.UnsendMyMessages",
            "Chat.UnsendMyMessagesAlertTitle",
            "Conversation.ChecksTooltip.Delivered",
            "Conversation.ChecksTooltip.Read",
            "Conversation.ContextMenuCancelEditing",
            "Conversation.ContextMenuCancelSending",
            "Conversation.ContextMenuCopy",
            "Conversation.ContextMenuCopyLink",
            "Conversation.ContextMenuDelete",
            "Conversation.ContextMenuForward",
            "Conversation.ContextMenuReply",
            "Conversation.ContextMenuSearchMessages",
            "Conversation.ContextMenuSendMessage",
            "Conversation.DeleteMessagesFor",
            "Conversation.DeleteMessagesForEveryone",
            "Conversation.DeleteMessagesForMe",
            "Conversation.DiscardVoiceMessageAction",
            "Conversation.DiscardVoiceMessageDescription",
            "Conversation.DiscardVoiceMessageTitle",
            "Conversation.EditingCaptionPanelTitle",
            "Conversation.EditingMessageMediaChange",
            "Conversation.EditingMessageMediaEditCurrentPhoto",
            "Conversation.EditingMessageMediaEditCurrentVideo",
            "Conversation.EditingMessagePanelMedia",
            "Conversation.EditingMessagePanelTitle",
            "Conversation.ErrorInaccessibleMessage",
            "Conversation.FilePhotoOrVideo",
            "Conversation.ForwardChats",
            "Conversation.ForwardContacts",
            "Conversation.ForwardTitle",
            "Conversation.HoldForVideo",
            "Conversation.InputTextAnonymousPlaceholder",
            "Conversation.InputTextCaptionPlaceholder",
            "Conversation.InputTextPlaceholder",
            "Conversation.InputTextPlaceholderComment",
            "Conversation.InputTextPlaceholderReply",
            "Conversation.InputTextSilentBroadcastPlaceholder",
            "Conversation.LinkDialogCopy",
            "Conversation.MessageDeliveryFailed",
            "Conversation.MessageDialogDelete",
            "Conversation.MessageDialogEdit",
            "Conversation.MessageDialogRetry",
            "Conversation.MessageDialogRetryAll",
            "Conversation.MessageEditedLabel",
            "Conversation.MessageViaUser",
            "Conversation.PinnedMessage",
            "Conversation.PrivateMessageLinkCopied",
            "Conversation.SavedMessages",
            "Conversation.ScheduleMessage.SendOn",
            "Conversation.ScheduleMessage.SendToday",
            "Conversation.ScheduleMessage.SendTomorrow",
            "Conversation.ScheduleMessage.Title",
            "Conversation.SendMessage.ScheduleMessage",
            "Conversation.SendMessage.SendSilently",
            "Conversation.SendMessage.SetReminder",
            "Conversation.SendMessageErrorTooMuchScheduled",
            "Conversation.SendingOptionsTooltip",
            "Conversation.StatusTyping",
            "Conversation.TapAndHoldToRecord",
            "Conversation.UnreadMessages",
            "Conversation.ViewMessage",
            "Message.Audio",
            "Message.Contact",
            "Message.File",
            "Message.ForwardedMessage",
            "Message.ForwardedMessageShort",
            "Message.Location",
            "Message.Photo",
            "Message.Sticker",
            "Message.Video",
            "Compose.TokenListPlaceholder",
            "Compose.NewGroup",
            "Compose.NewEncryptedChat",
            "Compose.Create",
            "Compose.NewChannel",
            "Compose.ChannelTokenListPlaceholder",
            "Compose.GroupTokenListPlaceholder",
            "Compose.ChannelMembers",
            "Conversation.typing",
            "Conversation.Call",
            "Conversation.Mute",
            "Conversation.Unmute",
            "Conversation.Edit",
            "Conversation.Info",
            "Conversation.Search",
            "Conversation.Location",
            "Conversation.Contact",
            "Conversation.EmptyPlaceholder",
            "Conversation.UnsupportedMedia",
            "Conversation.EncryptionWaiting",
            "Conversation.EncryptionProcessing",
            "Conversation.EncryptedPlaceholderTitleIncoming",
            "Conversation.EncryptedPlaceholderTitleOutgoing",
            "Conversation.EncryptedDescriptionTitle",
            "Conversation.EncryptedDescription1",
            "Conversation.EncryptedDescription2",
            "Conversation.EncryptedDescription3",
            "Conversation.EncryptedDescription4",
            "Conversation.StatusMembers_0",
            "Conversation.StatusMembers_1",
            "Conversation.StatusMembers_3_10",
            "Conversation.StatusMembers_many",
            "Conversation.StatusOnline_3_10",
            "Conversation.StatusOnline_any",
            "Conversation.Megabytes",
            "Conversation.Kilobytes",
            "Conversation.Bytes",
            "Conversation.ShareMyContactInfo",
            "Conversation.AddContact",
            "Conversation.SendMessage",
            "Conversation.EncryptionCanceled",
            "Conversation.DeleteManyMessages",
            "Conversation.SlideToCancel",
            "Conversation.OpenFile",
            "Conversation.ContextMenuShare",
            "Conversation.ContextMenuLookUp",
            "Conversation.SearchPlaceholder",
            "Conversation.SearchNoResults",
            "Conversation.StatusMembers_2",
            "Conversation.StatusMembers_any",
            "Conversation.StatusOnline_0",
            "Conversation.StatusOnline_1",
            "Conversation.StatusOnline_2",
            "Conversation.StatusOnline_many",
        }
        english = parse_strings_file(
            (IOS_APP / "en.lproj/Localizable.strings").read_text(encoding="utf-8")
        )
        chinese = parse_strings_file(
            (IOS_APP / "zh-Hans.lproj/Localizable.strings").read_text(encoding="utf-8")
        )

        self.assertEqual(set(), required_keys - english.keys())
        self.assertEqual(
            set(),
            required_keys - chinese.keys(),
            "the Simplified Chinese core conversation strings are incomplete",
        )

        placeholder_pattern = re.compile(r"%(?:\d+\$)?(?:\.\d+)?(?:@|d|f|s)")
        locale_neutral_keys = {
            "Conversation.Megabytes",
            "Conversation.Kilobytes",
            "Conversation.Bytes",
        }
        for key in sorted(required_keys):
            with self.subTest(key=key):
                self.assertTrue(chinese[key].strip())
                if key not in locale_neutral_keys:
                    self.assertNotEqual(english[key], chinese[key], f"{key} is still untranslated")
                self.assertEqual(
                    sorted(placeholder_pattern.findall(english[key])),
                    sorted(placeholder_pattern.findall(chinese[key])),
                    f"{key} must preserve its formatting placeholders",
                )

    def test_app_localizations_do_not_show_upstream_brand_or_links(self):
        resource_paths = (
            IOS_APP / "en.lproj/Localizable.strings",
            IOS_APP / "zh-Hans.lproj/Localizable.strings",
            IOS_APP / "zh-Hant.lproj/Localizable.strings",
        )
        residue = re.compile(r"telegram|t\.me(?:/|\b)", re.IGNORECASE)
        upstream_url = re.compile(
            r"https?://(?:[a-z0-9-]+\.)*telegram\.org(?:/|\b)"
            r"|https?://(?:www\.)?(?:telegram\.me|t\.me)(?:/|\b)",
            re.IGNORECASE,
        )
        link_destination = re.compile(r"\]\([^)]*\)")
        for path in resource_paths:
            with self.subTest(language=path.parent.name):
                values = parse_strings_file(path.read_text(encoding="utf-8"))
                matches = [
                    key
                    for key, value in values.items()
                    if residue.search(link_destination.sub("]()", value)) or upstream_url.search(value)
                ]
                self.assertEqual([], matches, f"{path.name} exposes upstream brand in: {matches[:12]}")

    def test_app_does_not_register_upstream_alternate_icons(self):
        import plistlib

        info = plistlib.loads((IOS_APP / "Info.plist").read_bytes())
        for key in ("CFBundleIcons", "CFBundleIcons~ipad"):
            self.assertNotIn("CFBundleAlternateIcons", info.get(key, {}))
        build = (ROOT / "Telegram/BUILD").read_text(encoding="utf-8")
        self.assertNotRegex(build, r"alternate_icons\s*=", "upstream icons must stay out of the built app")
        app_delegate = (ROOT / "submodules/TelegramUI/Sources/AppDelegate.swift").read_text(encoding="utf-8")
        self.assertRegex(app_delegate, r"getAvailableAlternateIcons:\s*\{\s*return \[\]")

        settings_search = (ROOT / "submodules/SettingsUI/Sources/Search/SettingsSearchableItems.swift").read_text(encoding="utf-8")
        self.assertNotIn('id: "appearance/app-icon"', settings_search)
        self.assertNotIn('id: "premium/app-icons"', settings_search)

        premium_intro = (ROOT / "submodules/PremiumUI/Sources/PremiumIntroScreen.swift").read_text(encoding="utf-8")
        self.assertNotIn("            .appIcons,\n", premium_intro[:premium_intro.index("init?(identifier:")])


if __name__ == "__main__":
    unittest.main()
