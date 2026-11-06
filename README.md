# Private Chat 私有聊天系统

Private Chat 是可自行部署和管理的聊天软件套件。本仓库把服务端、Android、iOS、macOS、Windows、Linux 客户端源码和项目文档合并到同一个 Git 仓库。

## 目录结构

- `server/`：Go 与 MTProto 服务端。
- `clients/android/`：Android 客户端。
- `clients/ios/`：iOS 客户端。
- `clients/desktop/`：macOS、Windows 和 Linux 桌面客户端。
- `docs/`：架构、迁移、发行和运维文档。
- `tests/`：仓库级检查。

当前套件包含 Android、iOS、macOS、Windows、Linux 五个平台客户端，没有独立的 Web 聊天客户端。

## 开发状态

五个 Private Chat 源码仓库的历史已导入本仓库。CI 覆盖仓库测试、客户端配置校验、部分离线服务端单测、Android Java 编译、iOS 无签名模拟器构建，以及 Ubuntu、Windows、macOS runner 上的桌面打包元数据检查；桌面端完整二进制构建尚未接入 CI。五个平台的登录、消息互通和文件传输尚未完成当前版本的端到端验证；完整中文本地化、所有 Telegram 品牌/UI 遗留项和正式发行也仍需逐项验证。源码合并或静态检查通过不代表这些发布要求已经完成。

## 本地服务端

服务端和本地开发依赖配置位于 `server/`，请先阅读其中的中文 README。`server/integration/README.md` 介绍隔离的依赖容器；`server/integration/LOCAL_RUNTIME.md` 说明如何启动本地 Go 服务和使用本机验证码 outbox。启动前须按文档检查并登记端口。不要提交 `.env`、本地数据库或对象存储数据、签名材料及生产凭据。

## 开发密钥

导入的上游源码包含开发用途密钥，例如 Android 开发签名 keystore 和服务端默认 RSA key。它们不适用于正式发布或生产部署。请在仓库之外生成和配置专用的生产签名密钥及 TLS 密钥；更换服务端 RSA key 时也要更新依赖其指纹的配置。

## 组件许可

每个组件分别保留自己的许可证和上游声明。请查看 `server/`、`clients/android/`、`clients/ios/`、`clients/desktop/`、`docs/` 中的许可文件。本仓库根目录的说明不会取代组件各自适用的许可条款。

## English Summary

Private Chat is a self-hosted messaging suite. This repository combines the server, Android and iOS apps, macOS, Windows and Linux desktop clients, and project documentation in one Git history.

CI currently runs repository checks, client configuration checks, scoped offline server tests, an unsigned Android Java compile, an unsigned iOS simulator build, and desktop packaging metadata checks on Ubuntu, Windows, and macOS runners. A full desktop binary build is not yet part of CI. Current-version login, messaging, and file-transfer flows across the five client platforms have not completed end-to-end validation. Complete Chinese localization, remaining Telegram-facing UI cleanup, and a production release also remain under validation. A source import or static check does not establish release readiness.

There is no standalone Web client. Each component retains its own license and upstream notices; see the license files in `server/`, `clients/android/`, `clients/ios/`, `clients/desktop/`, and `docs/`.

