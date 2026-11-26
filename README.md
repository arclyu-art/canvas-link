# CanvasLink

**简体中文** | [English](README.en.md)

**让 AI 在你的电脑上连接你自己的 Canvas。** Windows 本地工具，支持学校网页登录、SSO/MFA、本地 MCP 和可选的回环 HTTP 接口。

没有共享账号，没有预置学校或课程，没有作者服务器。每个人下载后在自己电脑上配置和登录。

使用前须确认学校和服务商允许此类接入。[Instructure API 政策](https://www.instructure.com/policies/canvas-api-policy)限制未经批准的 MCP 等接入；本项目尚无获得该批准的证据。学校禁止生成 Token 时，网页登录 Cookie 不能视为替代许可。限速和本地加密不能消除这一政策风险。

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

## 工作方式

CanvasLink 主要是复用用户登录会话的 Canvas API 客户端：向 `/api/v1` 发起请求并读取 JSON，也支持部分课程 HTML 和文件路径。它不是主要靠解析网页的传统爬虫，但仍属于第三方自动化访问；使用 API、登录 Cookie 或低频请求不等于获得学校和服务商的许可。

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
# 正式发布时，将 vX.Y.Z 替换为未使用的版本号：git tag vX.Y.Z; git push origin vX.Y.Z
```

发布前检查仓库没有自己的 config/session/snapshot。若曾误提交凭据，删除文件本身不够，必须撤销凭据并清理历史。

## 技术依据

- [MCP 官方 Python SDK 1.x](https://py.sdk.modelcontextprotocol.io/v1/)
- [MCP 本地服务连接](https://modelcontextprotocol.io/docs/develop/connect-local-servers)
- [Playwright 浏览器与 Chrome/Edge channel](https://playwright.dev/python/docs/browsers)
- [Playwright 与 PyInstaller](https://playwright.dev/python/docs/library#pyinstaller)
- [Windows DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)
- [Canvas API 分页](https://developerdocs.instructure.com/services/canvas/basics/file.pagination)

## 请求频率与可调限流

应用的 API 请求、分页和登录身份检查，共用按 Windows 用户、Canvas 站点持久化的额度：同一站点最多一个在途请求，默认间隔至少 **5 秒**，滚动一小时最多 **120 次**，滚动一天最多 **400 次**。状态保存在 `%LOCALAPPDATA%/CanvasLink/request-limits`；测试使用独立临时目录。旧版桥接也共享默认目录中的额度。重启或重新登录不会清零额度，请勿删除限流文件来绕过冷却。

- **429**：至少冷却 30 分钟；连续触发会延长，并遵守服务器更长的 `Retry-After`（秒数或 HTTP 日期）。
- **503**：冷却从 5 分钟开始。
- **401**：标记保存的 Canvas 会话失效，需要重新登录，不增加冷却。
- **403**：权限不足，不当作限流处理。
- **网络传输错误**：暂停 60 秒，不自动重试请求。

额度或冷却拦截会返回 `RATE_LIMITED` 和等待时间；可选本地 HTTP 接口返回 429，附带 `local_rate_limit=true`。这是本地拒绝，不是 Canvas 的响应，也不是成功的空列表。长时间冷却不会让进程一直睡眠等待；限流状态损坏时会阻止请求。

### 查看和修改设置

```powershell
.\CanvasLink.exe limits
.\CanvasLink.exe limits --interval 5 --hourly 120 --daily 400
```

可调范围：请求间隔 **3–60 秒**，小时额度 **10–300 次**，日额度 **10–1000 次**；小时额度不能大于日额度。设置按 Canvas 站点共享，每次请求重新加载。修改设置不清除历史请求或服务器冷却，也不能关闭串行限制及 429/503 冷却。查看和修改设置不会发送 Canvas 请求。

旧版命令行支持相同参数：`python bridge.py limits --interval 5 --hourly 120 --daily 400`。

按默认间隔，9 次请求的起始时间跨度至少约 40 秒，还需考虑网络耗时。这些限制只覆盖应用发出的请求，不覆盖浏览器页面资源或其他客户端。较长的自定义间隔、多页读取可能需要延长 AI 客户端或本地 HTTP 调用方的超时。建议先保持默认 5 秒间隔。
