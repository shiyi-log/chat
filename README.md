# Private Chat Documentation

`Private Chat` 是一套可自建的聊天系统，由私有消息服务端、Android、iOS、桌面客户端及本仓库的项目文档组成。这里的“私有”指服务可由操作者自行部署和管理。

## 套件仓库

| 仓库 | 范围 | 源码许可 |
| --- | --- | --- |
| [private-chat-server](https://github.com/shiyi-log/private-chat-server) | 基于 Teamgram 的 Go / MTProto 服务端 | Apache-2.0 |
| [private-chat-desktop](https://github.com/shiyi-log/private-chat-desktop) | Windows、Linux、macOS 桌面客户端 | GPL-3.0，保留 OpenSSL 链接例外；见该仓库 `LICENSE` |
| [private-chat-android](https://github.com/shiyi-log/private-chat-android) | Android 客户端 | GPL-2.0；见该仓库 `LICENSE` |
| [private-chat-ios](https://github.com/shiyi-log/private-chat-ios) | iOS 客户端 | 当前源码快照根目录缺少许可证文件；完整开源发行前须补齐对应上游许可及署名 |
| [private-chat-docs](https://github.com/shiyi-log/private-chat-docs) | 架构、任务与历史版本记录 | 本仓库原创文档采用 Apache-2.0；见 `LICENSE` |

macOS 端由 `private-chat-desktop` 覆盖。目前这五个仓库没有独立 Web 聊天客户端。服务端的 WebSocket 网关不等于浏览器聊天界面。

服务端保留 Teamgram 上游署名；客户端基于 Telegram 开源客户端源码快照，保留各自上游许可与第三方声明。各仓库的许可证分别适用；本仓库文档的 Apache-2.0 授权不改变客户端和第三方代码的许可。

## 当前源码预览范围（2026-11-03）

服务端 `v0.1.15-preview.1` 的范围是供本地评估的源码预览。默认 `none` 验证器已关闭：不返回验证码，也不再接受固定验证码。操作者接入并审查真实验证码提供方之前，默认配置不能完成账号登录。

历史文档中的固定验证码、默认密码和测试账号描述用于记录旧版本本地实验，不能作为当前预览版的操作说明。启动当前服务端前，应按服务端 README 设置独立的 MySQL、MinIO 和 Grafana 密码；Compose 发布端口默认绑定 `127.0.0.1`。

客户端当前默认 DC 地址仍面向本地开发：

- Desktop、iOS 模拟器：`127.0.0.1:10443`。
- Android 模拟器：`10.0.2.2:10443`，即模拟器访问宿主机的地址。
- 真机或跨机器部署需要改为可访问的局域网 IP 或域名，并保持服务端和客户端 MTProto 公钥一致。

当前源码公开不表示已经提供完整的正式客户端安装包。Android Debug、iOS 模拟器和 macOS Debug 的构建或运行验证记录见任务与版本文档；真机签名、正式更新、推送配置及多端联调仍有未完成项。

服务端预览版的定向验证包括禁用验证码提供方、运行时配置替换、Compose 配置和镜像构建检查。完整 `go test ./...` 仍有状态服务 KV 接口不兼容及测试环境缺少 FFmpeg 的失败。当前预览版尚未完成 Desktop / Android / iOS 全套登录、消息和文件上传端到端验证；旧版本 Android 双模拟器消息互发记录只适用于当时的本地配置。

## 文档索引

- [development-tasks.md](development-tasks.md)：开发任务与实施状态，顶部标注当前发行边界。
- [private-server-migration.md](private-server-migration.md)：原始架构迁移方案与接口定位，包含历史本地配置示例。
- [版本记录.md](版本记录.md)：历史版本变更记录，保留当时验证结果和限制。

修改方案时应同步更新任务状态，涉及服务地址、密钥、账号或生产拓扑的内容应使用脱敏示例，不在文档中保存真实凭据。版本记录保留历史事实；发行说明和当前任务状态用于说明新版本与旧实验的差异。

## English summary

Private Chat comprises five repositories: a Teamgram-based server, desktop clients for Windows/Linux/macOS, Android, iOS, and documentation. There is no standalone web chat client in this suite.

The server source preview disables the default verification provider. Sign-in requires a reviewed real provider. Current client addresses target local development, and complete cross-client sign-in, messaging, and upload validation remains outstanding. Upstream and third-party licenses apply independently in each repository; the Apache-2.0 license here covers original documentation only.
