# Chat Desktop 桌面端

这是 Chat 自托管聊天系统的桌面端源码，用于连接我们自建的服务端。本仓库不作为 Telegram Desktop 官方客户端发布，也不应使用 Telegram 品牌对外分发。

## 当前状态

- 内置生产和测试 DC 已指向本机本地运行时：`127.0.0.1:25222`，IPv6 本机地址为 `::1:25222`。
- 内置 MTProto RSA 公钥已替换为当前私有服务端公钥。
- Linux、Windows、macOS 的应用名称、图标、链接协议和高可见入口已纳入私有化配置检查。
- 私有化配置检查通过不代表桌面端已完成构建或登录验证。
- 当前桌面客户端的本地登录、消息收发和文件传输尚未完成端到端验证。

## 本地验证

运行桌面端私有化配置验证：

```sh
python3 scripts/verify_private_chat_desktop_config.py
```

验证覆盖：

- 私有 DC 地址与端口。
- macOS `Info.plist` 高可见名称。
- Windows 安装器、版本资源和 UWP/AppX 显示名称。
- Linux desktop/AppStream 元数据。
- 顶层 CMake/README 不再将本项目描述为官方 Telegram Desktop 发行版。

## 后续构建要求

- macOS：完整 Xcode 已就绪；仍需准备 Qt 6.11.1 和完整第三方库依赖。
- Linux：需要可用 Qt/CMake/Ninja 或可成功构建的 Docker 环境。
- Windows：需要 Visual Studio、Windows SDK、签名/打包配置。
- 跨设备测试：需要把 `127.0.0.1` 改为局域网 IP 或公网域名，并确保证书、端口和防火墙可访问。

## English Summary

This repository contains the Chat desktop client, configured for a self-hosted server. It is not an official Telegram Desktop distribution and should not be shipped with Telegram branding.
