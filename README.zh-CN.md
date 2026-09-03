# Grok 额度桌宠

**Grok usage desktop pet** · [English](README.md) · 中文

<p align="center">
  <img src="docs/preview.gif" alt="Grok 额度桌宠：SuperGrok、Grok Bot、Cursor、Codex 余量" />
</p>

Windows 上的非官方透明桌宠，用来看 SuperGrok 周额度、Grok Bot 周额度、Cursor 两个月额度池，以及 Codex（一条上深色 5 小时 / 浅色周额度）。不是 xAI、Cursor 或 OpenAI 官方软件。账单接口以后可能会变。

程序代码是 MIT。默认角色 Pip 是项目原创。加藤惠是可选的非官方同人主题，见 [ASSETS_NOTICE.md](ASSETS_NOTICE.md)。

## 安装

当前版本：**0.3.9**（GitHub 标签 `v0.3.9`）。

从 [最新 Release](https://github.com/MGMTopia/grok-usage-pet/releases/latest) 下载 **`GrokUsagePet-v0.3.9-Windows-x64.zip`**。不必装 Python，也不用自己编译。

1. 解压**整个文件夹**，不要只拷贝 exe。
2. 本机先登录一次（登哪个就显示哪条，不必一直开着对应软件）：
   - SuperGrok：安装 Grok CLI 后运行 `grok login`
   - Grok Bot 和 Cursor 额度：打开 Cursor 并登录
   - Codex：本机 ChatGPT 登录过 Codex（`codex login`），不要用纯 API Key 模式
3. 双击 `GrokUsagePet.exe`。

Windows 10/11。未签名，SmartScreen 可能要选「仍要运行」。

数据在 `%LOCALAPPDATA%\GrokUsagePet`。设置 → 卸载，或 `--uninstall`，只清本机集成和额度数据，不动 Grok / Cursor / Codex 登录。

更完整的操作说明：[使用说明.txt](使用说明.txt)

## 用法

- 平时只显示角色，窗口其余部分点得过去
- 鼠标靠近角色：展开额度条
- 鼠标停在某一条上：显示重置时间
- 鼠标离开：额度条收起
- 拖动角色移动位置
- 双击：固定 / 取消固定额度条
- 右键：刷新、设置主题或退出

设置 → 更新：可检查 GitHub 新版本。exe 会校验 SHA256 后再替换；源码运行只会打开网页。

## 反馈

用本仓库的 Issues、Discussions，或私密安全报告。不要贴 token、额度快照、`auth.json` 或完整日志。
