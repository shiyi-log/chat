# Chat Android 安卓端

这是 Chat 自托管聊天系统的 Android 客户端源码，用于连接我们自建的服务端。本仓库不作为 Telegram 官方 Android 客户端发布，也不应使用 Telegram 品牌对外分发。

## 当前状态

- 对外包名前缀已改为 `com.privatechat.messenger`。
- Debug/Beta 包名为 `com.privatechat.messenger.beta`。
- 默认应用显示名为 `Chat`，Beta 显示名为 `Chat Beta`。
- Android Debug 模拟器连接宿主机本地运行时：`10.0.2.2:35222`；其他构建默认端口为 `25222`。
- MTProto 握手公钥和 simple config 解密公钥已替换为当前私有服务端公钥。
- 当前已完成本机 `afatDebug` APK 构建，并在两台 Android 模拟器完成启动稳定性验证。

## 本地验证

运行 Android 私有化配置验证：

```sh
python3 scripts/verify_private_chat_android_config.py
```

验证覆盖：

- Gradle 包名、版本号和 Debug/Beta applicationId。
- Google Services / Huawei 配置中的对外包名。
- 默认英文应用名、登录验证码入口和联系人邀请入口高可见文案。
- Native 私有 DC 地址、端口、默认 DC 防御逻辑和服务端公钥存在性。
- README 不再保留官方发布说明。

## 本地构建

构建前需要自行配置由你管理、与目标服务端匹配的应用 API 参数。连接 Telegram 官方平台时应自行申请应用身份，不要复用上游或其他开发者的参数。

可在已经被 Git 忽略的根目录 `local.properties` 中填写：

```properties
PRIVATE_CHAT_API_ID=<你的正整数 API ID>
PRIVATE_CHAT_API_HASH=<你的 32 位十六进制 API hash>
```

也可以通过同名环境变量提供，环境变量优先。未配置或格式无效时 Gradle 会停止构建，仅显示缺失或无效的参数名，不输出参数值。不要提交 `local.properties` 或实际参数。

当前本机可用的调试包构建命令：

```sh
JAVA_HOME='/Applications/IntelliJ IDEA CE.app/Contents/jbr/Contents/Home' ./gradlew :TMessagesProj_App:assembleAfatDebug --stacktrace
```

调试 APK 输出路径：

```text
TMessagesProj_App/build/outputs/apk/afat/debug/app.apk
```

不需要 Android SDK 的应用参数配置测试：

```sh
python3 scripts/tests/test_private_chat_api_config.py
```

测试会在临时 Gradle 项目中运行实际参数加载脚本，使用虚构参数检查环境变量、本地配置、优先级和无效输入。默认使用本仓库 `gradlew`；也可通过 `PRIVATE_CHAT_GRADLE=/absolute/path/to/gradle` 指定已安装的 Gradle。

## 后续测试要求

- 真机测试需要把 `10.0.2.2` 改为局域网 IP 或公网域名，并确保服务端端口、防火墙和证书可访问。
- 发布变体需要从外部提供 `RELEASE_STORE_FILE`、`RELEASE_STORE_PASSWORD`、`RELEASE_KEY_ALIAS` 和 `RELEASE_KEY_PASSWORD`；这些值可通过 CI secret 注入，不能放进仓库里的 Gradle 属性文件。没有完整签名配置时，发行 APK 构建会失败。
- 正式发布还需要配置 Google/Firebase/Huawei 服务和推送证书。
- 当前还有深层 Premium、广告、Passport、故事等文案和功能入口需要继续按私有产品策略清理或隐藏。

## English Summary

This repository contains the Chat Android client, configured for a self-hosted server. It is not an official Telegram Android distribution and should not be shipped with Telegram branding.
