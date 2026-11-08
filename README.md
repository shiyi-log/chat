# Chat 聊天系统

Chat 是可自行部署和管理的聊天软件套件。本仓库统一维护服务端、Android、iOS、macOS、Windows、Linux 客户端源码和项目文档。

## 目录结构

- `server/`：Go 与 MTProto 服务端。
- `clients/android/`：Android 客户端。
- `clients/ios/`：iOS 客户端。
- `clients/desktop/`：macOS、Windows 和 Linux 桌面客户端。
- `clients/web/`：浏览器聊天客户端。
- `docs/`：架构、迁移、发行和运维文档。
- `tests/`：仓库级检查。

当前套件包含 Android、iOS、macOS、Windows、Linux 客户端，并提供仍在开发中的独立 Web 客户端。

## 开发状态

组件源码和文档现已合并到本仓库。常规 PR/main CI 覆盖仓库测试、客户端配置校验、部分离线服务端单测、Linux 服务端 11 个程序的预览构建与产物上传、Web 客户端协议检查/测试/静态构建与预览产物上传、Android `afatDebug` APK 预览构建、iOS 无签名模拟器构建与产物上传，以及 Ubuntu、Windows、macOS runner 上的桌面打包元数据检查。`v*-preview.*` 标签还会调用自托管 runner 构建三平台 Desktop Debug 包并汇总未签名预览候选；正式签名发行流程尚未接入。五个平台及 Web 的登录、消息互通和文件传输尚未完成当前版本的端到端验证；Web 客户端仍在开发中。完整中文本地化、所有 Telegram 来源 UI 遗留项和正式发行也仍需逐项验证。源码合并或预览构建通过不代表这些发布要求已经完成。

## 本地服务端

服务端和本地开发依赖配置位于 `server/`，请先阅读其中的中文 README。`server/integration/README.md` 介绍隔离的依赖容器；`server/integration/LOCAL_RUNTIME.md` 说明如何启动本地 Go 服务和使用本机验证码 outbox。启动前须按文档检查并登记端口。不要提交 `.env`、本地数据库或对象存储数据、签名材料及生产凭据。

## Web 客户端

本地 Web 客户端运行方式和服务端连接配置见 [`clients/web/README.md`](clients/web/README.md)。

## 开发密钥

导入的上游源码包含开发用途密钥，例如 Android 开发签名 keystore 和服务端默认 RSA key。它们不适用于正式发布或生产部署。请在仓库之外生成和配置专用的生产签名密钥及 TLS 密钥；更换服务端 RSA key 时也要更新依赖其指纹的配置。

## 组件许可

每个组件分别保留自己的许可证和上游声明。请查看 `server/`、`clients/android/`、`clients/ios/`、`clients/desktop/`、`docs/` 中的许可文件。本仓库根目录的说明不会取代组件各自适用的许可条款。

## English Summary

Chat is a self-hosted messaging suite. This repository maintains the server, Android and iOS apps, macOS, Windows and Linux desktop clients, and project documentation in one Git history.

Regular PR/main CI runs repository checks, client configuration checks, scoped offline server tests, a Linux preview build and upload of 11 server binaries, Web client protocol/tests/static build with a preview artifact, an Android `afatDebug` APK preview build, an unsigned iOS simulator build and artifact upload, and desktop packaging metadata checks on Ubuntu, Windows, and macOS runners. A `v*-preview.*` tag also calls self-hosted runners to build Debug desktop packages for all three platforms and assembles unsigned preview candidates; a signed production release workflow is not configured. Current-version login, messaging, and file-transfer flows across the five native platforms and Web have not completed end-to-end validation. The Web client remains in development, as do full Chinese localization and remaining Telegram-source UI cleanup. A source import or preview build does not establish release readiness.

The standalone Web client is under development in `clients/web/`. Each component retains its own license and upstream notices; see the license files in `server/`, `clients/android/`, `clients/ios/`, `clients/desktop/`, and `docs/`.

