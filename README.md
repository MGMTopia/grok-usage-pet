# Grok Usage Pet

一个常驻桌面的透明小宠物，用一眼能懂的方式显示 SuperGrok、Grok Bot 和
Cursor 额度与重置时间。当前版本：**0.3.1**。

<p>
  <img src="skins/original/app.png" alt="Original Pip theme" width="96">
  <img src="skins/megumi-kato/app.png" alt="Optional Megumi Kato fan theme" width="96">
</p>

> 非 xAI、Cursor 或 OpenAI 官方产品。程序代码采用 MIT 许可证；角色素材
> 另有边界说明，见 [ASSETS_NOTICE.md](ASSETS_NOTICE.md)。

## 下载与使用

从 [GitHub Releases](https://github.com/liruilong0805/grok-usage-pet/releases)
下载 `GrokUsagePet-v0.3.1-Windows-x64.zip`，完整解压后双击
`GrokUsagePet.exe`。Windows 10/11 无需安装 Python。

至少登录一个数据来源：

- SuperGrok：通过 Grok CLI 完成 `grok login`；
- Grok Bot / Cursor：在 Cursor 中登录。

鼠标靠近宠物会展开额度，悬停可看重置时间；拖动可移动，双击可在本次运行中固定，
右键可刷新、切换主题或退出。更完整的中文说明见
[docs/USAGE.zh-CN.md](docs/USAGE.zh-CN.md)。

## 主题

- **Original / Pip**：项目原创默认主题，可自由随 MIT 项目使用；
- **Megumi Kato**：可选的非官方同人主题，不属于 MIT 代码许可证，也不
  表示获得权利人授权。

程序只从 `skins/<id>/` 加载主题。主题缺失或损坏时会回退到 Original。

## 隐私

本项目没有遥测、广告、崩溃上报、机器指纹或自动更新。它读取本机已有的
Grok 与 Cursor 登录信息；Cursor 数据库以只读方式打开。Grok access token
过期时，会通过账户配置的 OIDC discovery 找到刷新地址，并原子更新原有
`auth.json`。

网络请求仅面向配置的 Grok OIDC issuer、`cli-chat-proxy.grok.com` 和
`api2.cursor.sh`。额度快照保存在 `%LOCALAPPDATA%\GrokUsagePet`，其中可能
包含 Cursor 邮箱、套餐和接口错误，应视为私人数据。详见
[SECURITY.md](SECURITY.md)。

## 从源码运行

需要 Python 3.12：

```powershell
python -m pip install -r requirements.txt
pythonw pet.py
```

离线测试不会联网、打开 Tk 窗口或读取真实凭据：

```powershell
powershell -File .\run-tests.ps1
```

Windows 发布包：

```powershell
python -m pip install -r requirements-build.txt
powershell -File .\pack-windows.ps1
```

构建脚本会测试、执行冻结版 smoke test、检查主题和敏感内容，再生成版本化
ZIP 与 SHA256。开发、架构和发布细节分别见
[DEVELOPMENT.md](docs/DEVELOPMENT.md)、[ARCHITECTURE.md](docs/ARCHITECTURE.md)
和 [PACKAGING.md](docs/PACKAGING.md)。

## 路线

近期重点是提升额度读取稳定性、主题制作体验和 Windows 发布质量。项目会
保持“Grok 额度桌宠”的清晰定位；暂不扩展成通用 AI Dashboard。

版本记录见 [CHANGELOG.md](CHANGELOG.md)。欢迎提交已脱敏的问题报告和小型
改进。代码许可证见 [LICENSE](LICENSE)。
