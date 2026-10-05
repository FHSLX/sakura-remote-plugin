# Sakura 手机远程端 · 插件

> 把手机变成 [Sakura Desktop Pet](https://github.com/Rvosy/sakura) 的第二个屏幕。
> **AI 计算和语音合成全部留在电脑**，手机只负责显示立绘、文字和播放语音 ——
> 所以手机不耗电、不发烫，也不需要对不同机型做性能适配。

**本仓库只有插件。** 配套的安卓 App 在另一个仓库：
[**FHSLX/sakura-APP**](https://github.com/FHSLX/sakura-APP)。

---

## 两个仓库的分工

| 仓库 | 用途 | 里面有什么 |
| :--- | :--- | :--- |
| **sakura-remote-plugin**（本仓库） | **插件源码**，提交给 [Sakura Registry](https://github.com/Rvosy/Sakura-Registry) 收录 | 只有插件：`plugin.yaml`、Python 源码、`static/` |
| [sakura-APP](https://github.com/FHSLX/sakura-APP) | **安卓 App 源码**，以及给普通用户下载的安装包 | 安卓工程 `phone_app/` + 文档 + Releases |

**为什么分开**：插件市场按「仓库根目录 = 插件」打包 —— 如果把安卓工程也放进来，
装插件的人会白下载一整个 Android 项目。反过来，用户下载 App 需要一个带 Releases 的仓库，
那里必须放 App 工程。

### 我要装哪个？

| 你想要 | 去哪里 |
| :--- | :--- |
| **手机上看立绘、听语音、当桌宠** | 两个都要装 → 到 [sakura-APP 的 Releases](https://github.com/FHSLX/sakura-APP/releases) 下载 **APK + 插件包** |
| **只用手机浏览器聊天** | 只装插件（本仓库）即可，不需要 App |

> **本仓库不提供 App 安装包。** 请到 [sakura-APP](https://github.com/FHSLX/sakura-APP) 下载。

---

## 这是什么

Sakura 官方自带一个可选的手机网页插件
[`sakura_mobile`（手机聊天）](https://github.com/Rvosy/sakura/tree/main/plugins/optional/sakura_mobile)，
本项目参考它做成，沿用了它验证过的 `sakura.host.mobile` 聊天链路与
`sakura.host.artifacts` 图片传递方式，并在此基础上把「手机端」从聊天页推进到了桌宠：

| | 官方 `sakura_mobile` | 本项目 |
| :--- | :--- | :--- |
| 定位 | 手机浏览器里**聊天** | 看**立绘**、听**语音**、还能当**桌宠** |
| 立绘 | 无 | 全屏立绘，按语气切换表情 |
| 语音 | 无 | 电脑合成、手机自动播放，文字跟着语音逐字出现 |
| 桌面立绘 | 无 | 悬浮窗，可拖动、可缩放、可缩成小球 |

只想用手机聊天的话，直接用官方那个插件就够了。

## 依赖

**仅 Python 标准库**，没有额外 Python 依赖。

需要宿主提供这些服务：

- `sakura.host.mobile` —— 聊天、历史、主题
- `sakura.host.artifacts` —— 图片上传
- `sakura.host.character` —— 解析角色包里的立绘
- `sakura.host.settings` —— 声明式设置面板

## 目录结构

```
plugin.yaml            插件清单（API v4）
plugin.py              插件入口，注册设置面板
http_server.py         HTTP 服务、路由、业务逻辑
web_ui.py              手机页面模板
config.json            默认配置（首次运行时作为模板）
restart_helper.ps1     远程重启 Sakura 的脚本
static/                前端资源（app.css / app.js / manifest）
```

浏览器打开的就是 `web_ui.py` 渲染的页面，它只依赖 `static/` 里的资源，
所以改前端不需要构建步骤 —— 页面会按文件修改时间自动加版本号。

## 安装

插件源码本身不需要构建。把本仓库的文件放到：

```
<Sakura安装目录>/plugins/user/sakura.remote/
```

然后在 Sakura → 设置 → **手机远程端** 里启用。

**完整安装步骤、配置项、疑难解答**见 [sakura-APP 的 README](https://github.com/FHSLX/sakura-APP)。
**插件内部实现与踩坑记录**见 [PLUGIN.md](PLUGIN.md)。

## 配置

| 字段 | 建议值 | 说明 |
| :--- | :--- | :--- |
| 监听地址 | `0.0.0.0` | 必须是这个，手机才能通过 WiFi 连上 |
| 端口 | `8770` | 默认即可 |
| **访问 token** | **改成随机长串** | 默认值是 `sakura`，务必改掉 |

> **安全提醒**：`0.0.0.0` 意味着同网段设备都能访问这个端口，靠 token 保护。
> 请改成足够长的随机串，并且**不要把端口映射到公网**。
> 需要外网访问请用组网工具（Tailscale / ZeroTier / 蒲公英）。

## 运行环境验证

- 电脑：Windows 10 / 11
- 手机：Android 10 及以上（Android 14+ 最稳妥）
- 已在 **Sakura v1.1.2 + 小米 Android 14（MIUI）** 上实测

## 许可证

[MIT License](LICENSE)，Copyright © 2026 FHSLX。

与 Sakura 官方的关系、灵感来源、角色资源归属等说明，见 [NOTICE](NOTICE)。
简单说：**这是第三方插件，与官方无隶属关系**；
角色资源的版权属于其原作者，本仓库不包含也不分发任何角色资源。
