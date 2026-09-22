# Sakura 手机远程端 · 插件

> 把手机变成 [Sakura Desktop Pet](https://github.com/Rvosy/sakura) 的第二个屏幕。
> **手机只负责显示和播放，模型推理与语音合成全部留在电脑** ——
> 所以手机不耗电、不发烫，也不需要对不同机型做性能适配。

本仓库只包含 **Sakura 插件**（供 Sakura 插件市场收录）。
配套的安卓 App 在另一个仓库：[**FHSLX/sakura-APP**](https://github.com/FHSLX/sakura-APP)。

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

## 组成

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

### 配套 App

桌面立绘、圆形小球、点击穿透这些体验需要安卓 App 的外壳能力 ——
插件自己能在手机浏览器里跑，但拿不到悬浮窗权限。
App 在 [FHSLX/sakura-APP](https://github.com/FHSLX/sakura-APP) 的 Releases 里下载。

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

## 实现说明

开发过程中踩过的坑、以及一些不那么直观的设计取舍，都记在
[PLUGIN.md](PLUGIN.md) 里（例如点击穿透为什么要分两步、
文字逐字显示为什么要等音频开始、拖动坐标为什么必须乘屏幕密度）。
那些都是实机验证出来的结论，改这块代码前值得先看一眼。

## 许可证

[MIT](LICENSE)

本项目与 Sakura 官方**无隶属关系**，是第三方插件。
角色资源的版权属于其原作者，本仓库不包含也不分发任何角色资源。
