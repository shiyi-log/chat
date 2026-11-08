# Chat 文档

Chat 是一套可自建的聊天系统，由服务端、Android、iOS、桌面客户端、独立 Web 客户端及本仓库的项目文档组成。服务可由操作者自行部署和管理。

## 单仓目录

| 目录 | 范围 | 源码许可 |
| --- | --- | --- |
| `server/` | 基于 Teamgram 的 Go / MTProto 服务端 | Apache-2.0；见目录内许可文件 |
| `clients/desktop/` | Windows、Linux、macOS 桌面客户端 | GPL-3.0，保留 OpenSSL 链接例外；见目录内 `LICENSE` |
| `clients/android/` | Android 客户端 | GPL-2.0；见目录内 `LICENSE` |
| `clients/ios/` | iOS 客户端 | GPL-2.0-or-later；保留上游及第三方许可声明 |
| `clients/web/` | 浏览器聊天客户端（开发中） | 发布前需补充或确认源码许可声明 |
| `docs/` | 架构、任务与历史版本记录 | 原创文档采用 Apache-2.0；见目录内 `LICENSE` |

macOS 端由 `clients/desktop/` 覆盖。`clients/web/` 是独立浏览器客户端，不等同于服务端 WebSocket 网关；当前支持手机号验证码登录、二步验证、注册、会话列表、历史消息和文本消息，附件及完整多客户端端到端验证仍未完成。

服务端保留 Teamgram 上游署名；客户端基于 Telegram 开源客户端源码快照，保留各自上游许可与第三方声明。各仓库的许可证分别适用；本仓库文档的 Apache-2.0 授权不改变客户端和第三方代码的许可。

## 当前本地验证边界（2026-11-08）

服务端默认 BFF 配置使用 `none` 验证码提供方，不发送验证码，也不接受固定验证码。隔离本地集成运行时会在运行目录内改用 `localfile` outbox，能验证本地请求链路，但不提供真实短信服务，也不代表生产登录可用。生产部署前仍需接入并审查真实验证码提供方。

历史文档中的固定验证码、默认密码和测试账号描述不能作为当前操作说明。启动服务端前，应按服务端 README 设置独立的 MySQL、MinIO 和 Grafana 密码；Compose 发布端口默认绑定 `127.0.0.1`。

客户端当前默认 DC 地址仍面向本地开发：

- Desktop、iOS 模拟器：`127.0.0.1:25222`。
- Android 模拟器：`10.0.2.2:25222`，即模拟器访问宿主机的地址。
- 真机或跨机器部署需要改为可访问的局域网 IP 或域名，并保持服务端和客户端 MTProto 公钥一致。

当前源码公开不表示已经提供完整的正式客户端安装包。CI 的 Android APK、iOS 模拟器包和三平台 Desktop 包均为调试或未签名预览产物；真机签名、正式更新、推送配置及多端联调仍有未完成项。预览标签候选构建与正式签名发行不同。

服务端 CI 运行选定的离线单元测试和本地运行配置测试；完整 `go test ./...` 仍有状态服务 KV 接口不兼容及测试环境缺少 FFmpeg 的失败。当前版本尚未完成 Desktop / Android / iOS / Web 全套登录、消息和文件上传端到端验证；旧版本 Android 双模拟器消息互发记录只适用于当时的本地配置。

## 文档索引

- [development-tasks.md](development-tasks.md)：开发任务与实施状态，顶部标注当前发行边界。
- [private-server-migration.md](private-server-migration.md)：原始架构迁移方案与接口定位，包含历史本地配置示例。
- [版本记录.md](版本记录.md)：历史版本变更记录，保留当时验证结果和限制。

修改方案时应同步更新任务状态，涉及服务地址、密钥、账号或生产拓扑的内容应使用脱敏示例，不在文档中保存真实凭据。版本记录保留历史事实；发行说明和当前任务状态用于说明新版本与旧实验的差异。

## English summary

Chat is maintained as one repository containing the Teamgram-based server, desktop clients for Windows/Linux/macOS, Android, iOS, a standalone Web client in development, and documentation.

The default server configuration disables the verification provider. The isolated local runtime uses a local-file outbox for development and does not send real SMS. Sign-in in production requires a reviewed real provider. CI artifacts are unsigned/debug previews, and complete cross-client sign-in, messaging, and upload validation remains outstanding. The Web source license declaration also needs resolution before distribution. Upstream and third-party licenses apply independently; the Apache-2.0 license here covers original documentation only.
