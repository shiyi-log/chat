# 私有聊天系统开发任务 / Private Chat Development Tasks

本文档用于管理四个本地仓库的开发任务：

- 服务端 / Server：`server`
- PC/Mac 桌面端 / Desktop：`desktop`
- iOS 端 / iOS：`ios`
- 安卓端 / Android：`android`

说明：当前 **Mac 桌面端包含在 `desktop` 仓库中**。如果后续决定单独支持 Telegram-Mac 原生 macOS 客户端，再新增第五个仓库和任务列表。

## 阶段 0：仓库基线 / Repository Baseline

- [x] 为 `server` 创建本地 Git 仓库。
- [x] 为 `server` 创建 `private-main` 分支。
- [x] 为 `desktop` 创建 `private-main` 分支。
- [x] 为 `ios` 创建 `private-main` 分支。
- [x] 为 `android` 创建 `private-main` 分支。
- [x] 将三端客户端原 Telegram 远程仓库保留为 `upstream`。
- [x] 提交安卓端已有的私有 `APP_ID` / `APP_HASH` 修改。
- [ ] 确定我们自己的 Git 托管地址。
- [ ] 为四个仓库添加我们自己的远程地址 / private remote。
- [ ] 推送四个仓库的 `private-main` 分支。

## 阶段 1：本地启动服务端 / Local Server Boot

目标：在本机用 Docker 启动 Teamgram，并确认客户端网关可连接。

- [ ] 检查 `server/docker-compose-env.yaml` 的端口和数据目录。
- [ ] 检查 `server/docker-compose.yaml` 的应用服务配置。
- [ ] 检查本机 Docker / Docker Compose 是否可用。
- [ ] 启动依赖服务：MySQL、Redis、etcd、Kafka、MinIO。
- [ ] 启动 Teamgram 应用服务。
- [ ] 验证客户端网关端口：
  - TCP `10443`
  - TCP `5222`
  - WebSocket `11443`
- [ ] 检查 `gnetway`、`session`、`bff`、`msg`、`sync` 日志。
- [ ] 确认默认登录验证码逻辑。
- [ ] 生产环境前替换默认/演示验证码逻辑。

## 阶段 2：服务端私有化配置 / Server Configuration

目标：把服务端变成我们自己的私有测试环境。

- [ ] 生成项目专用密钥和配置。
- [ ] 确认是否需要替换 Teamgram 默认服务端 RSA key。
- [ ] 配置私有服务器 IP / 域名。
- [ ] 修改数据库、Redis、MinIO 等默认账号密码。
- [ ] 整理必需环境变量。
- [ ] 关闭或替换演示账号、演示验证码。
- [ ] 确定第一版登录验证方式：
  - 本地固定验证码，仅测试使用
  - 后台可见验证码
  - 短信/邮箱验证码服务
- [ ] 写一份单服务器部署说明。

## 阶段 3：PC/Mac 桌面端 / Desktop Client

仓库：`desktop`

目标：桌面端连接我们自己的 Teamgram 服务端。

- [ ] 决定继续改当前桌面端，还是切换到 Teamgram 的 `teamgram-desktop` fork。
- [ ] 修改 `Telegram/SourceFiles/mtproto/mtproto_dc_options.cpp`。
- [ ] 将生产和测试 DC 1 指向我们的服务器 `SERVER_IP:10443`。
- [ ] 确认 Desktop 使用的 RSA 公钥是否需要和服务端替换。
- [ ] 如服务端 key 变更，同步替换 Desktop 内置 RSA 公钥。
- [ ] 配置私有 `TDESKTOP_API_ID` / `TDESKTOP_API_HASH`。
- [ ] 替换应用名称、图标、Bundle/App ID。
- [ ] 禁用或替换官方 Telegram 更新、崩溃上报、支持链接。
- [ ] 构建 macOS 桌面端。
- [ ] 按需构建 Windows / Linux 桌面端。
- [ ] 完成登录冒烟测试 / login smoke test。
- [ ] 完成私聊消息收发测试。

## 阶段 4：安卓端 / Android Client

仓库：`android`

目标：安卓端连接我们自己的 Teamgram 服务端。

- [x] 提交当前 `BuildVars.java` 中的私有 API 配置。
- [ ] 决定继续改当前安卓端，还是切换到 Teamgram 的 `teamgram-android` fork。
- [ ] 修改 `TMessagesProj/jni/tgnet/ConnectionsManager.cpp`。
- [ ] 在 `ConnectionsManager::initDatacenters()` 中将 DC 1 指向 `SERVER_IP:10443`。
- [ ] 检查 `TMessagesProj/jni/tgnet/Handshake.cpp` 中的 RSA 公钥逻辑。
- [ ] 如服务端 key 变更，同步替换 Android 内置 RSA 公钥。
- [ ] 替换包名、应用名、图标、通知渠道名称。
- [ ] 替换 Firebase / `google-services.json`。
- [ ] 禁用或替换官方 Telegram 支持、更新、上报接口。
- [ ] 构建 Debug APK。
- [ ] 完成登录冒烟测试。
- [ ] 完成私聊消息收发测试。

## 阶段 5：iOS 端 / iOS Client

仓库：`ios`

目标：iOS 端连接我们自己的 Teamgram 服务端。

- [ ] 决定继续改当前 iOS 端，还是切换到 Teamgram 的 `teamgram-ios` fork。
- [ ] 定位当前代码中的 `Network.swift` 或等效网络入口。
- [ ] 将 DC 1 的 `seedAddressList` 指向我们的服务器。
- [ ] 确认 iOS 端是否需要显式配置 `10443` 端口。
- [ ] 检查 `submodules/MtProtoKit/Sources/MTDatacenterAuthMessageService.m` 中的 RSA 公钥逻辑。
- [ ] 如服务端 key 变更，同步替换 iOS 内置 RSA 公钥。
- [ ] 在构建配置中设置私有 `api_id` / `api_hash`。
- [ ] 替换 Bundle ID、应用名、图标、URL Scheme、签名配置。
- [ ] 禁用或替换官方 Telegram 支持、更新、上报接口。
- [ ] 生成 Xcode 工程。
- [ ] 构建模拟器版本。
- [ ] 签名准备好后构建设备版本。
- [ ] 完成登录冒烟测试。
- [ ] 完成私聊消息收发测试。

## 阶段 6：多端互通 / Cross-Client Compatibility

目标：确认所有客户端都能通过我们的服务端互相通信。

- [ ] 在 PC/Mac 上创建测试用户 A。
- [ ] 在 Android 上创建测试用户 B。
- [ ] 在 iOS 上创建测试用户 C。
- [ ] 测试 A -> B 文本消息。
- [ ] 测试 B -> C 文本消息。
- [ ] 测试 C -> A 文本消息。
- [ ] 验证重启 App 后历史消息仍存在。
- [ ] 验证未读数。
- [ ] 验证联系人逻辑。
- [ ] 验证基础群聊。
- [ ] 验证小图片上传下载。
- [ ] 验证小文件上传下载。

## 阶段 7：产品私有化 / Product Fork Cleanup

目标：去掉官方品牌身份，形成我们自己的产品。

- [ ] 确定产品名称。
- [ ] 确定域名：
  - API/DC 域名
  - 官网域名
  - 支持域名
- [ ] 替换明显的官方品牌用户可见文案。
- [ ] 替换官方 Logo 和应用图标。
- [ ] 替换隐私政策、服务条款、支持链接。
- [ ] 替换崩溃上报和自动更新端点。
- [ ] 检查开源许可证和源码发布要求。
- [ ] 准备内测版本发布说明。

## 阶段 8：服务器部署 / Deployment

目标：部署到我们自己的服务器和域名。

- [ ] 确定服务器系统和配置。
- [ ] 安装 Docker 和 Docker Compose。
- [ ] 配置 DNS。
- [ ] 配置防火墙：
  - 开放 `10443`
  - 按需开放 `5222`
  - 按需开放 `11443`
  - 限制数据库和管理端口
- [ ] 配置持久化数据目录。
- [ ] 配置数据库备份。
- [ ] 配置日志轮转。
- [ ] 配置基础监控。
- [ ] 部署依赖服务。
- [ ] 部署应用服务。
- [ ] 使用所有客户端跑一轮冒烟测试。

## 第一轮开发建议 / First Sprint

第一轮只做最小闭环：

1. 本地启动 Teamgram 服务端。
2. 修改 PC/Mac 桌面端 DC 地址。
3. 验证 PC/Mac 能连到 Teamgram 登录流程。
4. 修改 Android DC 地址。
5. 验证 Android 能连到 Teamgram 登录流程。
6. 修改 iOS DC 地址。
7. 验证 iOS 能连到 Teamgram 登录流程。

以上完成后，再做品牌替换、正式密钥、生产部署。
