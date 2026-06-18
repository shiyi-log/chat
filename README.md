# Private Chat Desktop 桌面端

这是 `Private Chat` 私有聊天系统的桌面端源码快照，用于连接我们自建的 `private-chat-server`。当前仓库不再作为 Telegram Desktop 官方客户端发布，也不应使用 Telegram 品牌对外分发。

## 当前状态

- 内置生产和测试 DC 已指向本机私有服务端：`127.0.0.1:10443`，IPv6 本机地址为 `::1:10443`。
- 内置 MTProto RSA 公钥已替换为当前私有服务端公钥。
- Linux、Windows、macOS 的高可见入口正在分批改为 `Private Chat` / `Private Chat Desktop`。
- 本机仍缺完整桌面端构建环境，当前以静态配置验证为主。

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
- 顶层 CMake/README 不再保留官方发布说明。

## 后续构建要求

- macOS：需要完整 Xcode，而不是仅安装 Command Line Tools。
- Linux：需要可用 Qt/CMake/Ninja 或可成功构建的 Docker 环境。
- Windows：需要 Visual Studio、Windows SDK、签名/打包配置。
- 跨设备测试：需要把 `127.0.0.1` 改为局域网 IP 或公网域名，并确保证书、端口和防火墙可访问。

## English Summary

This repository is a private snapshot for `Private Chat Desktop`, configured for a self-hosted `private-chat-server`. It is not an official Telegram Desktop distribution and should not be shipped with Telegram branding.
