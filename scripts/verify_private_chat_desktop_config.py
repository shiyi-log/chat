#!/usr/bin/env python3
import plistlib
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def record(checks, ok, message):
    checks.append((ok, message))


def contains_all(text, values):
    return all(value in text for value in values)


def read_plist(path):
    with path.open("rb") as handle:
        return plistlib.load(handle)


def main():
    checks = []

    dc_path = "Telegram/SourceFiles/mtproto/mtproto_dc_options.cpp"
    dc_text = read_text(dc_path)
    official_dc_pattern = re.compile(r"\b(149\.154|91\.108)\.\d+\.\d+\b")
    record(checks, '{ 1, "127.0.0.1", 10443 }' in dc_text, f"{dc_path}：IPv4 DC 1 应指向 127.0.0.1:10443")
    record(checks, '{ 1, "::1", 10443 }' in dc_text, f"{dc_path}：IPv6 DC 1 应指向 ::1:10443")
    record(checks, dc_text.count("-----BEGIN RSA PUBLIC KEY-----") >= 2, f"{dc_path}：生产和测试 RSA 公钥应存在")
    record(checks, official_dc_pattern.search(dc_text) is None, f"{dc_path}：不应保留官方 DC IP")

    plist_path = "Telegram/Telegram.plist"
    plist = read_plist(ROOT / plist_path)
    record(checks, plist.get("CFBundleGetInfoString") == "Private Chat Desktop messaging app", f"{plist_path}：CFBundleGetInfoString 应为 Private Chat Desktop")
    url_schemes = plist.get("CFBundleURLTypes", [{}])[0].get("CFBundleURLSchemes", [])
    record(checks, "privatechat" in url_schemes, f"{plist_path}：URL scheme 应注册 privatechat")
    record(checks, "tg" not in url_schemes, f"{plist_path}：不应继续注册 tg URL scheme")

    cmake_path = "Telegram/CMakeLists.txt"
    cmake_text = read_text(cmake_path)
    record(checks, 'set(bundle_identifier "com.privatechat.desktop")' in cmake_text, f"{cmake_path}：Release Bundle ID 应为 com.privatechat.desktop")
    record(checks, 'set(bundle_identifier "com.privatechat.desktop$<$<CONFIG:Debug>:.debug>")' in cmake_text, f"{cmake_path}：Xcode Debug Bundle ID 应为 com.privatechat.desktop.debug")
    record(checks, 'set(output_name "Private Chat")' in cmake_text, f"{cmake_path}：macOS 输出名称应为 Private Chat")

    built_plist_path = ROOT / "out/Debug/Private Chat.app/Contents/Info.plist"
    if built_plist_path.exists():
        built_plist = read_plist(built_plist_path)
        record(checks, built_plist.get("CFBundleIdentifier") == "com.privatechat.desktop.debug", f"{built_plist_path.relative_to(ROOT)}：Debug Bundle ID 应为 com.privatechat.desktop.debug")
        record(checks, built_plist.get("CFBundleName") == "Private Chat", f"{built_plist_path.relative_to(ROOT)}：CFBundleName 应为 Private Chat")
    else:
        record(checks, True, "out/Debug/Private Chat.app 尚未生成，跳过生成产物 Bundle 元数据检查")

    setup_path = "Telegram/build/setup.iss"
    setup_text = read_text(setup_path)
    record(checks, contains_all(setup_text, [
        '#define MyAppShortName "Private Chat"',
        '#define MyAppName "Private Chat Desktop"',
        '#define MyAppPublisher "Private Chat"',
        '#define MyAppURL "https://private-chat.local"',
    ]), f"{setup_path}：Windows 安装器显示信息应指向 Private Chat")

    for rc_path, expected in [
        ("Telegram/Resources/winrc/Telegram.rc", "Private Chat Desktop"),
        ("Telegram/Resources/winrc/Updater.rc", "Private Chat Desktop Updater"),
    ]:
        rc_text = read_text(rc_path)
        record(checks, 'VALUE "CompanyName", "Private Chat"' in rc_text, f"{rc_path}：CompanyName 应为 Private Chat")
        record(checks, f'VALUE "FileDescription", "{expected}"' in rc_text, f"{rc_path}：FileDescription 应为 {expected}")
        record(checks, 'VALUE "ProductName", "Private Chat Desktop"' in rc_text, f"{rc_path}：ProductName 应为 Private Chat Desktop")

    appx_path = "Telegram/Resources/uwp/AppX/AppxManifest.xml"
    appx_text = read_text(appx_path)
    appx_root = ET.fromstring(appx_text)
    ns = {
        "f": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
        "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10",
        "uap3": "http://schemas.microsoft.com/appx/manifest/uap/windows10/3",
        "desktop": "http://schemas.microsoft.com/appx/manifest/desktop/windows10",
    }
    identity = appx_root.find("f:Identity", ns)
    properties = appx_root.find("f:Properties", ns)
    visual = appx_root.find(".//uap:VisualElements", ns)
    startup = appx_root.find(".//desktop:StartupTask", ns)
    record(checks, identity is not None and identity.get("Name") == "PrivateChat.Desktop", f"{appx_path}：Identity Name 应为 PrivateChat.Desktop")
    record(checks, identity is not None and identity.get("Publisher") == "CN=Private Chat", f"{appx_path}：Publisher 应为 CN=Private Chat")
    record(checks, properties is not None and properties.findtext("f:DisplayName", namespaces=ns) == "Private Chat Desktop", f"{appx_path}：DisplayName 应为 Private Chat Desktop")
    record(checks, properties is not None and properties.findtext("f:PublisherDisplayName", namespaces=ns) == "Private Chat", f"{appx_path}：PublisherDisplayName 应为 Private Chat")
    record(checks, visual is not None and visual.get("DisplayName") == "Private Chat Desktop", f"{appx_path}：VisualElements DisplayName 应为 Private Chat Desktop")
    record(checks, startup is not None and startup.get("DisplayName") == "Private Chat Desktop", f"{appx_path}：StartupTask DisplayName 应为 Private Chat Desktop")
    record(checks, "Telegram Desktop official messenger" not in appx_text, f"{appx_path}：不应保留官方 UWP 描述")
    protocol_names = [node.get("Name") for node in appx_root.findall(".//uap3:Protocol", ns)]
    record(checks, "privatechat" in protocol_names, f"{appx_path}：UWP 协议应注册 privatechat")
    record(checks, "tg" not in protocol_names, f"{appx_path}：UWP 协议不应继续注册 tg")

    desktop_path = "lib/xdg/org.telegram.desktop.desktop"
    desktop_text = read_text(desktop_path)
    record(checks, "Name=Private Chat" in desktop_text, f"{desktop_path}：Name 应为 Private Chat")
    record(checks, "Icon=com.privatechat.desktop" in desktop_text, f"{desktop_path}：Icon 应为 com.privatechat.desktop")
    record(checks, "x-scheme-handler/privatechat" in desktop_text, f"{desktop_path}：Linux 协议应注册 privatechat")
    record(checks, "x-scheme-handler/tg" not in desktop_text, f"{desktop_path}：Linux 协议不应继续注册 tg")

    metainfo_path = "lib/xdg/org.telegram.desktop.metainfo.xml"
    metainfo_text = read_text(metainfo_path)
    metainfo_root = ET.fromstring(metainfo_text)
    record(checks, metainfo_root.findtext("id") == "com.privatechat.desktop", f"{metainfo_path}：应用 ID 应为 com.privatechat.desktop")
    record(checks, metainfo_root.findtext("name") == "Private Chat", f"{metainfo_path}：名称应为 Private Chat")
    record(checks, "Private Chat is a private instant messaging client" in metainfo_text, f"{metainfo_path}：简介应说明私有客户端")

    root_cmake_path = "CMakeLists.txt"
    root_cmake_text = read_text(root_cmake_path)
    record(checks, 'DESCRIPTION "Private Chat Desktop messenger"' in root_cmake_text, f"{root_cmake_path}：项目描述应为 Private Chat Desktop")
    record(checks, 'HOMEPAGE_URL "https://private-chat.local"' in root_cmake_text, f"{root_cmake_path}：主页应为私有占位地址")

    variables_path = "cmake/variables.cmake"
    variables_text = read_text(variables_path)
    record(checks, "set(disable_autoupdate 1)" in variables_text, f"{variables_path}：默认应关闭自动更新")
    record(checks, 'option(DESKTOP_APP_DISABLE_AUTOUPDATE "Disable autoupdate." ${disable_autoupdate})' in variables_text, f"{variables_path}：自动更新开关应保留可显式覆盖入口")
    record(checks, 'option(DESKTOP_APP_DISABLE_CRASH_REPORTS "Disable crash report generation." ON)' in variables_text, f"{variables_path}：默认应关闭崩溃上报")

    application_path = "Telegram/SourceFiles/core/application.cpp"
    application_text = read_text(application_path)
    record(checks, '.protocol = u"privatechat"_q' in application_text, f"{application_path}：运行时应注册 privatechat URL scheme")
    record(checks, '.protocol = u"tg"_q' not in application_text, f"{application_path}：运行时不应继续注册 tg URL scheme")
    record(checks, 'protocolName = u"Private Chat Link"_q' in application_text, f"{application_path}：运行时协议名称应为 Private Chat Link")

    local_url_handlers_path = "Telegram/SourceFiles/core/local_url_handlers.cpp"
    local_url_handlers_text = read_text(local_url_handlers_path)
    record(checks, 'url.startsWith(u"privatechat://"_q, Qt::CaseInsensitive)' in local_url_handlers_text, f"{local_url_handlers_path}：应支持 privatechat:// 本地深链")
    record(checks, 'return u"tg://"_q + url.mid(u"privatechat://"_q.size())' in local_url_handlers_text, f"{local_url_handlers_path}：privatechat:// 应映射到现有本地处理流程")

    readme_path = "README.md"
    readme_text = read_text(readme_path)
    record(checks, readme_text.startswith("# Private Chat Desktop 桌面端"), f"{readme_path}：应使用 Private Chat 中文优先说明")
    record(checks, "official Telegram Desktop distribution" in readme_text, f"{readme_path}：应包含英文摘要说明非官方 Telegram 发布")

    failed = [message for ok, message in checks if not ok]
    passed_count = len(checks) - len(failed)

    if failed:
        print(f"Desktop 私有化配置验证失败：{passed_count}/{len(checks)} 项通过")
        for message in failed:
            print(f"- {message}")
        return 1

    print(f"Desktop 私有化配置验证通过：{passed_count}/{len(checks)} 项通过")
    print("- 内置 DC 已指向 127.0.0.1:10443 / ::1:10443")
    print("- macOS、Windows、UWP、Linux 高可见入口已指向 Private Chat")
    print("- 默认构建已关闭自动更新和崩溃上报，可在接入自建服务后显式打开")
    print("- 当前验证是静态配置验证；登录、多端互通、发布签名和正式服务器入口仍需单独验证")
    return 0


if __name__ == "__main__":
    sys.exit(main())
