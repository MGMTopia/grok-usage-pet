# Grok Usage Pet 使用说明

Grok Usage Pet 是 Windows 10/11 上的透明桌面宠物，用来查看 SuperGrok、
Grok Bot 和 Cursor 的额度与重置时间。它不是 xAI 或 Cursor 官方软件。

## 安装

1. 从 GitHub Releases 下载 Windows x64 ZIP。
2. 解压整个文件夹，不要只复制 EXE。
3. 至少登录一个数据来源：
   - SuperGrok：通过 Grok CLI 完成登录；
   - Grok Bot / Cursor：在 Cursor 中完成登录。
4. 双击 `GrokUsagePet.exe`。

首次运行未签名版本时，Windows SmartScreen 可能要求选择“仍要运行”。

## 使用

- 鼠标靠近宠物：展开额度条；
- 悬停额度：查看重置时间；
- 鼠标离开：收起额度条；
- 拖动宠物：移动位置；
- 双击：固定或取消固定额度条（仅本次运行，重启后默认收起）；
- 右键：刷新、设置主题或退出。

程序约每 60 秒刷新一次。如果只有一个服务已登录，另一个服务空白属于
正常情况。所有来源都失败时会保留上一次有效快照，不会用空数据覆盖。

## 隐私与安全

程序使用已有本地登录，不需要单独注册账号：

- 读取 Grok 的 `auth.json`；过期时可能通过 OIDC 刷新并原子写回 token；
- 以只读方式打开 Cursor 的 `state.vscdb`；
- 只访问配置的 Grok OIDC issuer、`cli-chat-proxy.grok.com` 和
  `api2.cursor.sh`；
- 不上传源码、项目文件、聊天或提示词；
- 没有遥测、广告或自动更新。

本地额度快照可能包含 Cursor 邮箱、套餐和错误信息，应视为私人数据。
完整说明见 [SECURITY.md](../SECURITY.md)。

## 主题

- `Original`：项目原创默认主题；
- `Megumi Kato`：非官方同人主题，不属于 MIT 代码许可证。

从旧可爱版升级时，v0.3 首次运行会在新目录没有同名文件的前提下，从
`%LOCALAPPDATA%\GrokUsagePetKawaii` 复制设置和最近额度快照到
`%LOCALAPPDATA%\GrokUsagePet`；旧目录不会被删除。

主题和角色素材边界见 [ASSETS_NOTICE.md](../ASSETS_NOTICE.md)。
