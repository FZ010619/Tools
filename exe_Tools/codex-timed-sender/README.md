# Codex 定时投递器

一个按需启动的 Windows 小工具：到点后将文字、选择的本地文件路径和可选图片投递到你明确绑定的 Codex / ChatGPT 桌面应用窗口。

## 下载与运行

在 Releases 下载 `CodexTimedSender.exe` 后直接运行。它不需要安装 Python。

## 从源码运行

```powershell
python -m pip install -r requirements.txt
python app.py
```

## 构建可执行文件

```powershell
python -m pip install -r requirements-build.txt
./build.ps1
```

生成的文件位于 `dist/CodexTimedSender.exe`。构建产物默认被 Git 忽略；请通过 GitHub Release 分发。

## 使用

1. 打开目标 Codex 或 ChatGPT 对话，并点击它的输入框。
2. 在小工具中点击“3 秒后绑定当前窗口”，并在倒计时内切回该对话。
3. 填入文字；本地文件会以路径清单发送；图片会作为剪贴板图片粘贴。
4. 设置未来的发送时间，选择与你的应用设置一致的 Enter 或 Ctrl+Enter，点击“开始倒计时”。
5. 最后五秒可随时点击“取消计划”。

发送前程序会再次校验目标窗口。窗口已关闭、变更或无法切到前台时，程序不会输入任何内容。

## 限制

- 仅支持 Windows，且 Codex / ChatGPT 与本程序应以相同权限运行。
- 一次只能计划一条投递；不保存历史、多项目列表或后台常驻。
- 本地文件仅发送路径。目标 Codex 项目是否能够读取该路径取决于其项目目录与权限。
- 发送会覆盖系统剪贴板内容。
- Windows 可能阻止后台程序强制切换前台窗口；程序会等待短暂时间，若无法激活目标窗口则取消发送而不误投递。

## 隐私与安全

- 不联网，不收集或上传数据。
- 仅在你明确绑定的单一窗口存在且可激活时才发送。
- 请勿在待发送文本中放入密码、令牌或其他不应发送给聊天服务的敏感信息。

## 许可证

[MIT License](LICENSE)。
