# CanvasLink

**让 AI 在你的电脑上连接你自己的 Canvas。** Windows 本地工具，支持学校网页登录、SSO/MFA、本地 MCP 和可选的回环 HTTP 接口。

没有共享账号，没有预置学校或课程，没有作者服务器。每个人下载后在自己电脑上配置和登录。

**[下载 Windows 本地版](https://github.com/arclyu-art/canvas-link/releases/latest/download/CanvasLink-windows-x64.zip)** · [全部 Releases](https://github.com/arclyu-art/canvas-link/releases)

## Windows：下载后怎么用

1. 在本项目的 **Releases** 下载 `CanvasLink-windows-x64.zip`，完整解压。
2. 双击 `CanvasLink.exe`。保留旁边的 `_internal` 文件夹，不能只复制 EXE。
3. 填自己的学校 Canvas 地址，例如 `https://school.instructure.com`，点击“保存设置”。
4. 点击“登录 Canvas”，在独立 Edge/Chrome 窗口完成学校登录和 MFA。验证真实 Canvas 身份后窗口关闭。
5. 点击“检查连接”，确认上游登录有效。
6. 点击“复制 MCP 配置”，添加到支持 **本地 stdio MCP** 的 AI 客户端。

Windows 10/11 x64，需要已安装 Microsoft Edge 或 Google Chrome。此包不需要用户另外安装 Python，不捆绑整套浏览器。初版未做数字签名。

普通网页登录成功不等于本工具的独立浏览器已登录。会话过期时需要重新点登录；不会绕过学校的 MFA。

## AI 可以做什么

- 读取课程、作业要求、截止时间、rubric 和自己的提交状态。
- 查看课程页面、模块、文件目录与公告。
- 用经过同源分页校验的接口获取完整列表。
- 根据读取到的资料总结、复习、规划。定时提醒由 AI 客户端的调度能力提供，本程序不会自动给任何人创建任务。
- 默认只读。可选修改请求仍需用户在本机逐次确认。

不是任意网页里的 AI 都能访问你电脑。本程序提供本地 MCP；客户端必须支持启动本地 MCP 子进程。它不附带模型、AI 账号或模型 API key。

MCP 配置示例（实际路径由设置窗口自动生成）：

```json
{
  "mcpServers": {
    "canvas-link": {
      "command": "C:\\Apps\\CanvasLink\\CanvasLink.exe",
      "args": ["mcp"]
    }
  }
}
```

配置里没有 Canvas 密码、Cookie 或本地 HTTP 密钥。MCP 子进程在用户自己的 Windows 身份下读取加密会话。MCP stdout 只输出协议数据。

## 你的数据存在哪

个人设置和 DPAPI 加密会话默认在 `%LOCALAPPDATA%\CanvasLink`，不在解压目录。密码不保存；普通浏览器配置不读取；学校 SSO 存储不导出。清除登录可删除本机保存的 Canvas 会话。

连接 AI 后，你请求读取的课程资料会交给该 AI 客户端及其模型服务。详见 [PRIVACY.md](PRIVACY.md)。

## 高级设置与限制

- 默认登录路径 `/login`。学校要求 SAML 时可以自行改为 `/login/saml`。
- 遇到登录连接重置可以尝试“连接兼容模式”；不会自动关闭 TLS 验证。
- 学校策略、浏览器自动化限制或 API 权限可能让部分学校无法使用。不是所有 Canvas 功能都有同等可用的 API。
- Gradescope、出版社、外部 LTI 平台不等于 Canvas，需要单独授权和接入。
- 文件下载如返回外部签名链接，本工具不会携带 Canvas Cookie 自动跟过去。
- 写入仅支持 JSON/form API 请求，不支持多阶段大文件上传。每次本地确认的预览最大 4000 字符。
- 一次响应最多 16 MiB；列表最多 100 页/20000 条。遇到限制应缩小查询。
- 初版仅支持 Windows；没有验证 macOS/Linux。MCP SDK 使用明确固定的 1.x 维护线版本，避免自动跨大版本改变协议适配。

## 命令行

```powershell
.\CanvasLink.exe setup https://school.instructure.com
.\CanvasLink.exe login
.\CanvasLink.exe status
.\CanvasLink.exe list '/api/v1/courses?enrollment_state=active&per_page=100'
.\CanvasLink.exe get '/api/v1/users/self/profile'
.\CanvasLink.exe logout
.\CanvasLink.exe mcp-config
.\CanvasLink.exe doctor --browser-check
```

可选旧式本地端口：`CanvasLink.exe serve --port 8766`。使用同一用户身份的 Python 客户端可调用 `canvaslink.core.http_call()`。这个端口不是网页公开接口，必须通过本机认证；MCP 不依赖它，也不需要先启动它。

## 开发 / 从源码运行

安装 Python 3.11+，在 Windows 项目目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m canvaslink
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe build_windows.py
.\.venv\Scripts\python.exe release.py
```

不复制任何人的会话进行测试。测试为临时 `CANVASLINK_DATA_DIR` 创建合成数据；不会读取默认用户目录或真实 Canvas。

## 上传 GitHub

此目录就是独立仓库内容。上传本目录中的源码文件，而不是它外层的私人工作区。`release.py` 通过文件白名单生成干净源码包。

包含 MIT License、隐私说明、安全边界、测试与 GitHub Actions。Actions 会在 Windows 上测试及构建；推送 `v*` 标签时生成 GitHub Release，并附 Windows ZIP 和 SHA256。

```powershell
git init
git add .
git commit -m "Initial CanvasLink release"
# 按 GitHub 新仓库页面设置 remote，再 push。
# 正式发布版本时：git tag v0.1.0; git push origin v0.1.0
```

发布前检查仓库没有自己的 config/session/snapshot。若曾误提交凭据，删除文件本身不够，必须撤销凭据并清理历史。

## 技术依据

- [MCP 官方 Python SDK 1.x](https://py.sdk.modelcontextprotocol.io/v1/)
- [MCP 本地服务连接](https://modelcontextprotocol.io/docs/develop/connect-local-servers)
- [Playwright 浏览器与 Chrome/Edge channel](https://playwright.dev/python/docs/browsers)
- [Playwright 与 PyInstaller](https://playwright.dev/python/docs/library#pyinstaller)
- [Windows DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)
- [Canvas API 分页](https://developerdocs.instructure.com/services/canvas/basics/file.pagination)
