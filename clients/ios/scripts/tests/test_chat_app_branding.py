import json
import re
import shutil
import struct
import subprocess
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
            "zh-hans\nzh-hant\nzh-hans\nzh-hans\nzh-Hans\nzh-Hant\nStart Messaging\n开始聊天\n開始聊天\nen\nfr\n",
            result.stdout,
        )

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
