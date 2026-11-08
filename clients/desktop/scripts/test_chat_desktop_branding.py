#!/usr/bin/env python3
import plistlib
import re
import struct
import unittest
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANGUAGE_PATTERN = re.compile(
    r'^[ \t]*"(?P<key>[^"]+)"\s*=\s*"(?P<value>(?:\\.|[^"\\])*)";',
    re.MULTILINE,
)
PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z][a-zA-Z0-9_]*)\}")
CHAT_ICON_COLORS = {(20, 91, 87), (244, 162, 97), (255, 255, 255)}


def read_text(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def read_strings(relative_path):
    return {
        match.group("key"): match.group("value")
        for match in LANGUAGE_PATTERN.finditer(read_text(relative_path))
    }


def png_colors(data):
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError("icon asset is not a PNG image")

    offset = 8
    compressed = bytearray()
    width = height = color_type = bit_depth = None
    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        chunk = data[offset + 8:offset + 8 + length]
        if kind == b"IHDR":
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
            if compression or filtering or interlace or bit_depth != 8:
                raise AssertionError("icon PNG uses an unsupported encoding")
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            break
        offset += length + 12

    bytes_per_pixel = {2: 3, 6: 4}.get(color_type)
    if bytes_per_pixel is None:
        raise AssertionError("icon PNG must use RGB or RGBA pixels")

    raw = zlib.decompress(compressed)
    stride = width * bytes_per_pixel
    previous = bytearray(stride)
    colors = set()

    def paeth(left, above, upper_left):
        estimate = left + above - upper_left
        distances = (abs(estimate - left), abs(estimate - above), abs(estimate - upper_left))
        return (left, above, upper_left)[distances.index(min(distances))]

    for row in range(height):
        start = row * (stride + 1)
        filter_type = raw[start]
        scanline = bytearray(raw[start + 1:start + 1 + stride])
        for index, value in enumerate(scanline):
            left = scanline[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            above = previous[index]
            upper_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            if filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            elif filter_type == 4:
                predictor = paeth(left, above, upper_left)
            elif filter_type == 0:
                predictor = 0
            else:
                raise AssertionError(f"unsupported PNG filter: {filter_type}")
            scanline[index] = (value + predictor) & 0xFF

        for index in range(0, stride, bytes_per_pixel):
            colors.add(tuple(scanline[index:index + 3]))
        previous = scanline

    return colors


def ico_png_images(data):
    reserved, image_type, count = struct.unpack_from("<HHH", data)
    if reserved != 0 or image_type != 1:
        raise AssertionError("app icon must be a Windows ICO file")
    images = []
    for index in range(count):
        entry = struct.unpack_from("<BBBBHHII", data, 6 + index * 16)
        size, offset = entry[6], entry[7]
        image = data[offset:offset + size]
        if image.startswith(b"\x89PNG\r\n\x1a\n"):
            images.append(image)
    return images


class ChatDesktopBrandingTests(unittest.TestCase):
    def test_disabled_updater_links_to_chat_releases_on_every_platform(self):
        source = read_text("Telegram/SourceFiles/core/update_checker.cpp")
        update = re.search(
            r"void UpdateApplication\(\) \{(?P<body>.*?)\n\}",
            source,
            re.DOTALL,
        )
        self.assertIsNotNone(update)
        body = update.group("body")
        self.assertIn("https://github.com/shiyi-log/chat/releases", body)
        self.assertNotRegex(
            body,
            re.compile(r"(?:telegram\.org|telegram-desktop|org\.telegram\.desktop)", re.IGNORECASE),
        )

    def test_core_conversation_strings_are_available_in_simplified_chinese(self):
        base = read_strings("Telegram/Resources/langs/lang.strings")
        chinese = read_strings("Telegram/Resources/langs/zh-Hans.strings")
        required = {
            "lng_chat_status_unaccessible",
            "lng_chat_status_members#one",
            "lng_chat_status_members#other",
            "lng_chat_status_online#one",
            "lng_chat_status_online#other",
            "lng_chat_status_members_online",
            "lng_chat_status_subscribers#one",
            "lng_chat_status_subscribers#other",
            "lng_chat_status_direct",
            "lng_attach_replace",
            "lng_attach_failed",
            "lng_attach_file",
            "lng_attach_photo",
            "lng_attach_camera",
            "lng_attach_document",
            "lng_attach_photo_or_video",
            "lng_attach_profile_emoji",
            "lng_send_button",
            "lng_send_silent_message",
            "lng_send_text_no",
            "lng_send_text_no_about",
            "lng_send_text_type_and_last",
            "lng_send_image_empty",
            "lng_send_images_selected#one",
            "lng_send_images_selected#other",
            "lng_send_files_selected#one",
            "lng_send_files_selected#other",
            "lng_send_grouped",
            "lng_send_compressed_one",
            "lng_send_compressed",
            "lng_send_high_quality",
            "lng_send_as_documents_one",
            "lng_send_as_documents",
            "lng_send_media_invalid_files",
            "lng_message_empty",
            "lng_message_unsupported",
            "lng_message_not_found",
            "lng_message_ph",
            "lng_message_stars_ph#one",
            "lng_message_stars_ph#other",
            "lng_message_tagged_with",
            "lng_scheduled_messages",
            "lng_scheduled_messages_empty",
            "lng_scheduled_date",
            "lng_scheduled_date_until_online",
            "lng_scheduled_send_until_online",
            "lng_scheduled_send_now",
            "lng_dialogs_text_with_from",
            "lng_dialogs_text_from_wrapped",
            "lng_dialogs_text_media",
            "lng_dialogs_text_media_wrapped",
            "lng_dialogs_text_from_in_topic",
            "lng_forward_choose",
            "lng_forward_cant",
            "lng_forward_send",
            "lng_forward_messages#one",
            "lng_forward_messages#other",
            "lng_forward_title",
            "lng_forward_about",
            "lng_forward_many_about",
            "lng_forward_show_sender",
            "lng_forward_show_senders",
            "lng_forward_show_caption",
            "lng_forward_show_captions",
            "lng_forward_change_recipient",
            "lng_forward_sender_names_removed",
            "lng_forward_header_short",
            "lng_reply_in_another_title",
            "lng_reply_in_another_chat",
            "lng_reply_in_author",
            "lng_reply_in_chats_list",
            "lng_reply_show_in_chat",
            "lng_reply_remove",
            "lng_reply_about_quote",
            "lng_reply_options_header",
            "lng_reply_options_quote",
            "lng_reply_header_short",
            "lng_reply_quote_selected",
            "lng_reply_from_private_chat",
            "lng_reply_quote_long_title",
            "lng_reply_quote_long_text",
            "lng_search_back_to_results",
            "lng_search_results_header",
            "lng_search_found_results#one",
            "lng_search_found_results#other",
            "lng_search_messages_from",
            "lng_search_messages_n_of_amount",
        }
        self.assertTrue(required <= base.keys())
        self.assertTrue(required <= chinese.keys())
        for key in required:
            with self.subTest(key=key):
                self.assertEqual(
                    sorted(PLACEHOLDER_PATTERN.findall(base[key])),
                    sorted(PLACEHOLDER_PATTERN.findall(chinese[key])),
                )

    def test_language_share_uses_the_chat_deep_link(self):
        source = read_text("Telegram/SourceFiles/boxes/language_box.cpp")
        share = re.search(
            r"void Rows::share\(.*?(?=\n}\n\nvoid Rows::remove)",
            source,
            re.DOTALL,
        )
        self.assertIsNotNone(share)
        self.assertIn('u"privatechat://setlanguage/"_q', share.group())
        self.assertNotRegex(share.group(), re.compile(r"t\.me|telegram", re.IGNORECASE))

    def test_crash_report_copy_is_localized_and_uses_chat_branding(self):
        source = read_text("Telegram/SourceFiles/core/crash_report_window.cpp")
        self.assertNotRegex(
            source,
            re.compile(r'u"[^\"]*(?:\bTelegram\b|telegram\.org|telegramcrash)[^\"]*"', re.IGNORECASE),
        )
        self.assertIn("https://github.com/shiyi-log/chat/releases", source)

        base = read_strings("Telegram/Resources/langs/lang.strings")
        chinese = read_strings("Telegram/Resources/langs/zh-Hans.strings")
        required = {
            "lng_crash_report_last_closed",
            "lng_crash_report_last_crashed",
            "lng_crash_report_get_latest",
            "lng_crash_report_file_title",
            "lng_crash_report_file_filter",
            "lng_crash_report_local_copy",
            "lng_crash_report_save_button",
            "lng_crash_report_continue",
        }
        self.assertTrue(required <= base.keys())
        self.assertTrue(required <= chinese.keys())
        for key in required:
            self.assertEqual(
                sorted(PLACEHOLDER_PATTERN.findall(base[key])),
                sorted(PLACEHOLDER_PATTERN.findall(chinese[key])),
                key,
            )

    def test_crash_reports_are_saved_locally_without_uploading_to_upstream(self):
        source = read_text("Telegram/SourceFiles/core/crash_report_window.cpp")
        header = read_text("Telegram/SourceFiles/core/crash_report_window.h")
        self.assertNotIn("tdesktop.com/crash.php", source)
        self.assertNotIn("sendReport()", source)
        self.assertNotIn("QNetworkAccessManager", header)
        self.assertIn(
            "connect(&_send, &QPushButton::clicked, [=] { saveReport(); });",
            source,
        )
        self.assertIn("file.write(getCrashReportRaw());", source)

    def test_platform_shell_surfaces_use_chat_branding_and_chinese_menu_copy(self):
        mac_menu = read_text("Telegram/SourceFiles/platform/mac/global_menu_mac.mm")
        linux_menu = read_text("Telegram/SourceFiles/platform/linux/main_window_linux.cpp")
        main_window = read_text("Telegram/SourceFiles/window/main_window.cpp")
        notifications = read_text("Telegram/SourceFiles/window/notifications_manager_default.cpp")
        updater = read_text("Telegram/SourceFiles/_other/updater_win.cpp")

        for path, source, legacy in (
            ("macOS menu", mac_menu, 'u"About Telegram"_q'),
            ("macOS app menu", mac_menu, '_menuBar->addMenu(u"Telegram"_q)'),
            ("macOS show menu", mac_menu, 'u"Show Telegram"_q'),
            ("Linux quit menu", linux_menu, 'lt_telegram, u"Telegram"_q'),
            ("Linux about menu", linux_menu, 'lt_telegram,\n\t\t\tu"Telegram"_q'),
            ("empty window title", main_window, 'u"Telegram"_q'),
            ("private notification title", notifications, 'u"Telegram Desktop"_q'),
            ("Windows update error", updater, 'L"Failed to update Telegram'),
        ):
            with self.subTest(surface=path):
                self.assertNotIn(legacy, source)

        self.assertIn('u"Chat"_q', mac_menu)
        self.assertIn("tr::lng_mac_menu_show(tr::now)", mac_menu)
        self.assertIn('lt_telegram, u"Chat"_q', linux_menu)
        self.assertIn('u"Chat"_q', main_window)
        self.assertIn('u"Chat"_q', notifications)
        self.assertIn('L"Failed to update Chat', updater)

        base = read_strings("Telegram/Resources/langs/lang.strings")
        chinese = read_strings("Telegram/Resources/langs/zh-Hans.strings")
        required = {
            "lng_mac_menu_hide_telegram",
            "lng_mac_menu_show",
            "lng_mac_menu_quit_telegram",
            "lng_mac_menu_about_telegram",
        }
        self.assertTrue(required <= base.keys())
        self.assertTrue(required <= chinese.keys())
        for key in required:
            with self.subTest(locale="zh-Hans", key=key):
                self.assertEqual(
                    sorted(PLACEHOLDER_PATTERN.findall(base[key])),
                    sorted(PLACEHOLDER_PATTERN.findall(chinese[key])),
                )
        self.assertEqual("隐藏 {Chat}", chinese["lng_mac_menu_hide_telegram"])
        self.assertEqual("显示 Chat", chinese["lng_mac_menu_show"])
        self.assertEqual("退出 {Chat}", chinese["lng_mac_menu_quit_telegram"])
        self.assertEqual("关于 {Chat}", chinese["lng_mac_menu_about_telegram"])

    def test_new_install_defaults_to_simplified_chinese_without_overriding_saved_language(self):
        language = read_text("Telegram/SourceFiles/lang/lang_keys.cpp")
        application = read_text("Telegram/SourceFiles/core/application.cpp")
        self.assertIn('kDefaultLanguage = "zh-Hans"_cs', language)
        self.assertIn("if (langpack().id().isEmpty())", application)
        self.assertIn("langpack().switchToId(Lang::BundledChineseLanguage())", application)

    def test_about_and_entry_surfaces_use_chat_identity_and_local_project_links(self):
        paths = (
            "Telegram/SourceFiles/boxes/about_box.cpp",
            "Telegram/SourceFiles/intro/intro_start.cpp",
            "Telegram/SourceFiles/settings/sections/settings_notifications.cpp",
        )
        forbidden = re.compile(
            r"\bTelegram\b|telegram\.org|github\.com/telegramdesktop|tdesktop\.com",
            re.IGNORECASE,
        )
        for path in paths:
            source = read_text(path)
            source = re.sub(r"\A/\*.*?\*/", "", source, flags=re.DOTALL)
            literals = re.findall(r'(?:u8|u|U|L)?"((?:\\.|[^"\\])*)"', source)
            with self.subTest(path=path):
                self.assertEqual([], [value for value in literals if forbidden.search(value)])

        about = read_text(paths[0])
        intro = read_text(paths[1])
        notifications = read_text(paths[2])
        self.assertIn('box->setTitle(u"Chat"_q);', about)
        self.assertIn('setTitleText(rpl::single(u"Chat"_q));', intro)
        self.assertIn('elided(u"Chat"_q', notifications)
        self.assertIn("https://github.com/shiyi-log/chat", about)
        application = read_text("Telegram/SourceFiles/core/application.cpp")
        changelog = re.search(
            r"QString Application::changelogLink\(\) const \{(?P<body>.*?)\n\}",
            application,
            re.DOTALL,
        )
        self.assertIsNotNone(changelog)
        self.assertIn("https://github.com/shiyi-log/chat/releases", changelog.group("body"))

        base = read_strings("Telegram/Resources/langs/lang.strings")
        chinese = read_strings("Telegram/Resources/langs/zh-Hans.strings")
        required = {
            "lng_about_text1",
            "lng_about_text1_api",
            "lng_about_text2",
            "lng_about_text3",
            "lng_about_text3_faq",
        }
        self.assertTrue(required <= chinese.keys())
        for key in required:
            self.assertEqual(
                sorted(PLACEHOLDER_PATTERN.findall(base[key])),
                sorted(PLACEHOLDER_PATTERN.findall(chinese[key])),
                key,
            )

    def test_runtime_language_packs_do_not_expose_telegram_brand_or_links(self):
        brand_pattern = re.compile(r"telegram|t\.me", re.IGNORECASE)
        old_product_name = "Private Chat"
        for path in (
            "Telegram/Resources/langs/lang.strings",
            "Telegram/Resources/langs/cloud_lang.strings",
            "Telegram/Resources/langs/zh-Hans.strings",
            "Telegram/Resources/langs/en.lproj/Localizable.strings",
        ):
            with self.subTest(path=path):
                values = read_strings(path)
                matches = [key for key, value in values.items() if brand_pattern.search(value)]
                self.assertEqual([], matches, f"runtime language values contain legacy brand: {matches[:8]}")
                old_names = [key for key, value in values.items() if old_product_name in value]
                self.assertEqual([], old_names, f"runtime language values contain the old product name: {old_names[:8]}")

    def test_qr_logos_use_the_chat_bubble_mark(self):
        header = read_text("Telegram/SourceFiles/intro/intro_qr.h")
        intro = read_text("Telegram/SourceFiles/intro/intro_qr.cpp")
        connection = read_text("Telegram/SourceFiles/boxes/connection_box.cpp")

        self.assertIn("ChatQrLogoImage", header)
        self.assertNotIn("TelegramLogoImage", header)
        for path, source in (
            ("intro QR", intro),
            ("connection QR", connection),
        ):
            with self.subTest(path=path):
                self.assertIn("ChatQrLogoImage()", source)
                self.assertNotIn("introQrPlane", source)
        self.assertIn("bubble.addRoundedRect", intro)

    def test_offline_chinese_pack_uses_known_keys_and_placeholders(self):
        base = read_strings("Telegram/Resources/langs/lang.strings")
        self.assertTrue((ROOT / "Telegram/Resources/langs/zh-Hans.strings").is_file())
        chinese = read_strings("Telegram/Resources/langs/zh-Hans.strings")

        self.assertGreaterEqual(len(chinese), 40)
        self.assertTrue(
            {"lng_menu_settings", "lng_start_msgs", "lng_intro_about"}
            <= chinese.keys()
        )
        self.assertTrue(all(key in base for key in chinese))
        for key, value in chinese.items():
            self.assertEqual(
                sorted(PLACEHOLDER_PATTERN.findall(base[key])),
                sorted(PLACEHOLDER_PATTERN.findall(value)),
                key,
            )
        self.assertEqual("设置", chinese["lng_menu_settings"])
        self.assertEqual("开始聊天", chinese["lng_start_msgs"])

    def test_offline_chinese_pack_covers_auth_recovery_and_clipboard_feedback(self):
        base = read_strings("Telegram/Resources/langs/lang.strings")
        chinese = read_strings("Telegram/Resources/langs/zh-Hans.strings")
        required = {
            "lng_code_block_header_copy",
            "lng_intro_fragment_about",
            "lng_intro_fragment_button",
            "lng_signin_no_email_forgot",
            "lng_signin_cant_email_forgot",
            "lng_signin_reset_account",
            "lng_signin_sure_reset",
            "lng_signin_reset",
            "lng_signin_reset_wait",
            "lng_signin_reset_in_days",
            "lng_signin_reset_in_hours",
            "lng_signin_reset_cancelled",
            "lng_signin_banned_text",
            "lng_signin_banned_help",
            "lng_code_copied",
        }

        self.assertTrue(required <= base.keys())
        self.assertTrue(
            required <= chinese.keys(),
            "the Simplified Chinese auth recovery strings are incomplete",
        )
        for key in sorted(required):
            with self.subTest(locale="zh-Hans", key=key):
                self.assertNotEqual(base[key], chinese[key], f"{key} is still untranslated")
                self.assertEqual(
                    sorted(PLACEHOLDER_PATTERN.findall(base[key])),
                    sorted(PLACEHOLDER_PATTERN.findall(chinese[key])),
                    key,
                )

    def test_offline_chinese_pack_is_in_the_runtime_resource_bundle(self):
        tree = ET.parse(ROOT / "Telegram/Resources/qrc/telegram/telegram.qrc")
        files = [node.text for node in tree.findall(".//file")]
        resource_path = "../../langs/zh-Hans.strings"

        self.assertIn(resource_path, files)
        self.assertTrue(
            (ROOT / "Telegram/Resources/qrc/telegram" / resource_path).resolve().is_file()
        )

    def test_first_run_uses_bundled_chinese_without_overriding_a_saved_language(self):
        application = read_text("Telegram/SourceFiles/core/application.cpp")
        instance = read_text("Telegram/SourceFiles/lang/lang_instance.cpp")

        self.assertTrue("langpack().id().isEmpty()" in application)
        self.assertTrue("BundledChineseLanguage()" in application)
        self.assertIn('u"zh-Hans"_q', instance)
        self.assertIn(':/langs/zh-Hans.strings', instance)

    def test_packaged_application_displays_chat_brand(self):
        plist_path = ROOT / "Telegram/Telegram.plist"
        with plist_path.open("rb") as stream:
            plist = plistlib.load(stream)
        manifest = ET.parse(ROOT / "Telegram/Resources/uwp/AppX/AppxManifest.xml")
        namespaces = {"f": "http://schemas.microsoft.com/appx/manifest/foundation/windows10"}
        properties = manifest.find("f:Properties", namespaces)
        desktop_entry = read_text("lib/xdg/org.telegram.desktop.desktop")
        setup = read_text("Telegram/build/setup.iss")

        self.assertEqual("Chat Desktop messaging app", plist["CFBundleGetInfoString"])
        self.assertEqual("Chat", properties.findtext("f:DisplayName", namespaces=namespaces))
        self.assertIn('#define MyAppShortName "Chat"', setup)
        self.assertIn("Name=Chat\n", desktop_entry)

    def test_linux_package_launch_metadata_matches_chat_executable(self):
        cmake = read_text("Telegram/CMakeLists.txt")
        desktop_entry = read_text("lib/xdg/org.telegram.desktop.desktop")
        dbus_service = read_text("lib/xdg/org.telegram.desktop.service")
        metainfo = read_text("lib/xdg/org.telegram.desktop.metainfo.xml")
        snapcraft = read_text("snap/snapcraft.yaml")

        self.assertIn('set(output_name "Chat")', cmake)
        self.assertIn("TryExec=Chat", desktop_entry)
        self.assertIn("Exec=Chat -- %U", desktop_entry)
        self.assertIn("Exec=Chat -quit", desktop_entry)
        self.assertIn("@CMAKE_INSTALL_FULL_BINDIR@/Chat", dbus_service)
        self.assertIn("<binary>Chat</binary>", metainfo)
        self.assertIn(
            "desktop: usr/share/applications/com.privatechat.desktop.desktop",
            snapcraft,
        )
        self.assertIn(
            "parse-info: [usr/share/metainfo/com.privatechat.desktop.metainfo.xml]",
            snapcraft,
        )
        self.assertIn("name: chat-shiyi-log", snapcraft)
        self.assertIn("  chat:\n    command: usr/bin/Chat", snapcraft)
        self.assertIn("common-id: com.privatechat.desktop", snapcraft)
        self.assertNotIn("org.telegram.desktop", snapcraft)
        self.assertNotIn("telegram-desktop", snapcraft)
        self.assertIn("APP_ID=com.privatechat.desktop", snapcraft)

    def test_desktop_confirmation_and_authorization_surfaces_use_chat_brand(self):
        authorization = read_text("Telegram/SourceFiles/api/api_authorizations.cpp")
        external_control = read_text("Telegram/SourceFiles/core/external_control.cpp")

        self.assertIn('u"Chat Desktop%1"_q', authorization)
        self.assertNotIn("Telegram Desktop%1", authorization)
        self.assertIn('u"本地自动化"_q', external_control)
        self.assertIn('{ u"启用"_q, enable }', external_control)
        self.assertIn('{ u"取消"_q, cancel }', external_control)
        self.assertIn('{ u"不确定"_q, cancel }', external_control)
        self.assertIn("Chat 桌面端", external_control)
        self.assertIn("Chat 窗口", external_control)
        self.assertNotIn('u"Telegram Desktop over the local socket', external_control)
        self.assertNotIn('u"Telegram window to enable"', external_control)

    def test_windows_package_and_update_paths_match_chat_executable(self):
        manifest = ET.parse(ROOT / "Telegram/Resources/uwp/AppX/AppxManifest.xml")
        namespaces = {"f": "http://schemas.microsoft.com/appx/manifest/foundation/windows10"}
        application = manifest.find("f:Applications/f:Application", namespaces)
        setup = read_text("Telegram/build/setup.iss")
        startup = read_text("Telegram/SourceFiles/_other/startup_task_win.cpp")
        updater = read_text("Telegram/SourceFiles/_other/updater_win.cpp")

        self.assertEqual("Chat.exe", application.get("Executable"))
        self.assertIn('#define MyAppExeName "Chat.exe"', setup)
        self.assertIn(r'Source: "{#ReleasePath}\Chat.exe"', setup)
        self.assertIn(r'UninstallDisplayIcon={app}\Chat.exe', setup)
        self.assertIn(r'directory + L"\\Chat.exe"', startup)
        self.assertIn('exeName = L"Chat.exe";', updater)
        self.assertIn('equal(tofname, updateTo + L"Telegram.exe")', updater)

    def test_packaged_application_icons_use_chat_art(self):
        icon_paths = (
            "Telegram/Telegram/Images.xcassets/Icon.iconset/icon_512x512@2x.png",
            "Telegram/Telegram/Images.xcassets/Icon.appiconset/icon512@2x.png",
            "Telegram/Resources/art/icon512.png",
        )
        for path in icon_paths:
            with self.subTest(path=path):
                self.assertTrue(
                    CHAT_ICON_COLORS <= png_colors((ROOT / path).read_bytes())
                )

        ico_images = ico_png_images(
            (ROOT / "Telegram/Resources/art/icon256.ico").read_bytes()
        )
        self.assertTrue(ico_images, "Windows app icon must contain a PNG image")
        self.assertTrue(any(CHAT_ICON_COLORS <= png_colors(image) for image in ico_images))

    def test_uwp_application_icons_use_chat_art(self):
        assets = ROOT / "Telegram/Resources/uwp/AppX/Assets"
        icon_paths = sorted(assets.rglob("*.png"))
        self.assertTrue(icon_paths)

        for path in icon_paths:
            colors = png_colors(path.read_bytes())
            with self.subTest(path=path.relative_to(ROOT)):
                if "_altform-unplated" in path.name:
                    self.assertIn((255, 255, 255), colors)
                    self.assertTrue(
                        (20, 91, 87) not in colors and (244, 162, 97) not in colors
                    )
                else:
                    self.assertTrue(CHAT_ICON_COLORS <= colors)

    def test_active_tray_icon_uses_the_chat_bubble_vector(self):
        tray_path = ROOT / "Telegram/Resources/icons/tray_monochrome.svg"
        tray = ET.parse(tray_path).getroot()
        serialized = ET.tostring(tray, encoding="unicode")
        app_icon = ET.parse(ROOT / "Telegram/Resources/art/chat_logo.svg").getroot()
        app_icon_serialized = ET.tostring(app_icon, encoding="unicode").upper()
        self.assertIn("#145B57", app_icon_serialized)
        self.assertIn("#F4A261", app_icon_serialized)
        self.assertIn("#FFFFFF", app_icon_serialized)
        self.assertIn("M53,17h26", serialized)
        self.assertIn("M17,28h42", serialized)

    def test_secondary_user_visible_surfaces_use_chat_branding(self):
        webview = read_text("Telegram/Resources/bot_webview_shell_html/page.js")
        linux_shell = read_text(
            "Telegram/SourceFiles/ui/chat/attach/attach_bot_webview_linux_shell.cpp"
        )
        recorder = read_text("Telegram/SourceFiles/ui/controls/round_video_recorder.cpp")
        mime_types = read_text("Telegram/SourceFiles/core/mime_type.cpp")
        file_utilities = read_text("Telegram/SourceFiles/core/file_utilities.cpp")
        base_language = read_strings("Telegram/Resources/langs/lang.strings")
        chinese_language = read_strings("Telegram/Resources/langs/zh-Hans.strings")

        self.assertNotIn("|| 'Telegram'", webview)
        self.assertIn("|| 'Chat'", webview)
        self.assertNotIn("document.title = 'Telegram';", linux_shell)
        self.assertIn("document.title = 'Chat';", linux_shell)
        self.assertIn('u"Chat"_q.toUpper()', recorder)
        self.assertNotIn('u"Telegram"_q.toUpper()', recorder)
        self.assertIn('tr::lng_mime_type_chat_sticker(tr::now)', mime_types)
        self.assertNotIn('u"Telegram sticker (*.tgs)"_q', mime_types)
        self.assertEqual(base_language["lng_mime_type_chat_sticker"], "Chat sticker (*.tgs)")
        self.assertEqual(chinese_language["lng_mime_type_chat_sticker"], "Chat 贴纸（*.tgs）")
        self.assertIn('return u"Chat Lite"_q;', file_utilities)
        self.assertNotIn('return u"Telegram Lite"_q;', file_utilities)


if __name__ == "__main__":
    unittest.main(verbosity=2)
