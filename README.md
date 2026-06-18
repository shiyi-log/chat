# Private Chat iOS 端

这是 `Private Chat` 私有聊天系统的 iOS 客户端源码快照，用于连接我们自建的 `private-chat-server`。当前仓库不再作为 Telegram 官方 iOS 客户端发布，也不应使用 Telegram 品牌对外分发。

## 当前状态

- 默认应用显示名已改为 `Private Chat`。
- 默认 Bundle ID 已改为 `com.privatechat.ios`。
- 默认 URL Scheme 已改为 `privatechat`。
- iOS 模拟器默认连接宿主机私有服务端：`127.0.0.1:10443`。
- MTProto 认证公钥和备用配置解密公钥已替换为当前私有服务端公钥。
- 当前已完成本地静态配置验证；尚未生成 Xcode 工程，也未构建模拟器或真机包。

## 本地验证

运行 iOS 私有化配置验证：

```sh
python3 scripts/verify_private_chat_ios_config.py
```

验证覆盖：

- `build-system/template_minimal_development_configuration.json` 中的 Bundle ID、URL Scheme 和待替换占位项。
- `Telegram/Telegram-iOS/Config-Fork.xcconfig` 中的应用名、Bundle ID 和 URL Scheme。
- `Telegram/Telegram-iOS/Info.plist` 中的 URL Scheme、权限文案和主题文件类型。
- 分享扩展登录提示。
- iOS 网络 seed DC 地址和端口。
- README 私有化说明。

## 构建前置条件

iOS 端完整构建仍需要：

- 完整 Xcode，而不是只安装 Command Line Tools。
- Apple Developer Team ID。
- 可用签名证书和 provisioning profile。
- 私有项目的 `api_id` 和 `api_hash`。
- 真机测试时需要把 `127.0.0.1` 改为局域网 IP 或公网域名。

生成工程前必须先替换：

```text
build-system/template_minimal_development_configuration.json
```

其中 `api_id`、`api_hash`、`team_id` 目前故意保留为占位值，避免误判为可发布配置。

## 本地构建入口

准备好完整 Xcode 和私有配置后，可继续使用原构建入口生成 Xcode 工程：

```sh
python3 build-system/Make/Make.py \
    --cacheDir="$HOME/private-chat-ios-bazel-cache" \
    generateProject \
    --configurationPath=build-system/template_minimal_development_configuration.json \
    --xcodeManagedCodesigning
```

如果只做模拟器构建，可按需禁用 provisioning profile；真机和发布包必须使用真实签名配置。

## 后续测试要求

- 生成 Xcode 工程。
- 构建模拟器版本。
- 使用私有服务端完成登录冒烟测试。
- 真机签名准备好后构建设备版本。
- 使用固定局域网 IP 或公网域名完成 Android / iOS / Desktop 多端互通测试。

## English Summary

This repository is a private iOS client snapshot for `Private Chat`, configured for a self-hosted `private-chat-server`. It is not an official Telegram iOS distribution and should not be shipped with Telegram branding.
