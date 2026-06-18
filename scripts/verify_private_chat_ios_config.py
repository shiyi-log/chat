#!/usr/bin/env python3
import json
import plistlib
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def record(checks, ok, message):
    checks.append((ok, message))


def parse_xcconfig(text):
    values = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def has_placeholder(value):
    return isinstance(value, str) and value.startswith("{!") and value.endswith("!}")


def main():
    checks = []

    template_path = "build-system/template_minimal_development_configuration.json"
    template = json.loads(read_text(template_path))
    record(checks, template.get("bundle_id") == "com.privatechat.ios", f"{template_path}：bundle_id 应为 com.privatechat.ios")
    record(checks, template.get("app_specific_url_scheme") == "privatechat", f"{template_path}：app_specific_url_scheme 应为 privatechat")
    for key in ("api_id", "api_hash", "team_id"):
        record(checks, has_placeholder(template.get(key)), f"{template_path}：{key} 仍应明确保留为待替换占位值")

    xcconfig_path = "Telegram/Telegram-iOS/Config-Fork.xcconfig"
    xcconfig = parse_xcconfig(read_text(xcconfig_path))
    record(checks, xcconfig.get("APP_NAME") == "Private Chat", f"{xcconfig_path}：APP_NAME 应为 Private Chat")
    record(checks, xcconfig.get("APP_BUNDLE_ID") == "com.privatechat.ios", f"{xcconfig_path}：APP_BUNDLE_ID 应为 com.privatechat.ios")
    record(checks, xcconfig.get("APP_SPECIFIC_URL_SCHEME") == "privatechat", f"{xcconfig_path}：APP_SPECIFIC_URL_SCHEME 应为 privatechat")

    info_plist_path = "Telegram/Telegram-iOS/Info.plist"
    with (ROOT / info_plist_path).open("rb") as handle:
        info = plistlib.load(handle)

    url_schemes = []
    for item in info.get("CFBundleURLTypes", []):
        url_schemes.extend(item.get("CFBundleURLSchemes", []))
    record(checks, "privatechat" in url_schemes, f"{info_plist_path}：URL Scheme 应包含 privatechat")
    record(checks, "telegram" not in url_schemes, f"{info_plist_path}：URL Scheme 不应再包含显式 telegram")

    permission_keys = [
        "NSContactsUsageDescription",
        "NSLocationAlwaysUsageDescription",
        "NSLocationWhenInUseUsageDescription",
        "NSMotionUsageDescription",
    ]
    for key in permission_keys:
        record(checks, "Private Chat" in info.get(key, ""), f"{info_plist_path}：{key} 应包含 Private Chat")

    theme_types = info.get("UTImportedTypeDeclarations", [])
    theme_identifiers = [item.get("UTTypeIdentifier") for item in theme_types]
    theme_descriptions = [item.get("UTTypeDescription", "") for item in theme_types]
    record(checks, "com.privatechat.ios.theme" in theme_identifiers, f"{info_plist_path}：主题 UTI 应为 com.privatechat.ios.theme")
    record(checks, any("Private Chat" in value for value in theme_descriptions), f"{info_plist_path}：主题文件说明应包含 Private Chat")

    share_path = "Telegram/Share/en.lproj/Localizable.strings"
    share_text = read_text(share_path)
    record(checks, 'Share.AuthTitle" = "Log in to Private Chat"' in share_text, f"{share_path}：分享扩展登录标题应包含 Private Chat")
    record(checks, 'Share.AuthDescription" = "Open Private Chat and log in to share."' in share_text, f"{share_path}：分享扩展登录说明应包含 Private Chat")

    network_path = "submodules/TelegramCore/Sources/Network/Network.swift"
    network_text = read_text(network_path)
    has_private_dc = bool(re.search(r"1:\s*\[\s*\"127\.0\.0\.1\"\s*\]", network_text))
    has_private_port = "port: 10443" in network_text
    official_dc_pattern = re.compile(r"\b(149\.154|91\.108)\.\d+\.\d+\b")
    record(checks, has_private_dc, f"{network_path}：DC 1 seed 地址应指向 127.0.0.1")
    record(checks, has_private_port, f"{network_path}：DC 端口应为 10443")
    record(checks, official_dc_pattern.search(network_text) is None, f"{network_path}：不应保留官方 DC IP")

    failed = [message for ok, message in checks if not ok]
    passed_count = len(checks) - len(failed)

    if failed:
        print(f"iOS 私有化配置验证失败：{passed_count}/{len(checks)} 项通过")
        for message in failed:
            print(f"- {message}")
        return 1

    print(f"iOS 私有化配置验证通过：{passed_count}/{len(checks)} 项通过")
    print("- Bundle ID、应用名和 URL Scheme 已指向 Private Chat 私有配置")
    print("- 本地模板仍明确保留 api_id、api_hash、team_id 占位值，生成工程前必须替换")
    print("- iOS 网络 seed DC 1 已指向 127.0.0.1:10443，本地模拟器可用于后续连接验证")
    return 0


if __name__ == "__main__":
    sys.exit(main())
