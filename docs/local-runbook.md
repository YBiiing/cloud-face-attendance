# 本地运行手册

## P1-01 页面与 API 骨架

当前只有首页、静态资源、存活检查与 API 文档。无需数据库即可验证骨架。Docker/MySQL/Redis 将在 P1 后续任务接入；下面的 Windows 虚拟环境仅用于当前 HTTP 骨架验证，不代表模型容器兼容性已验证。

在 PowerShell 中运行：

```powershell
Set-Location E:\A-project\cloud-face-attendance
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.in
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

访问 `http://127.0.0.1:8000/`，接口文档为 `/api/docs`，存活检查为 `/api/health/live`。按 Ctrl+C 停止；不删除数据。依赖完整锁定在模型兼容验证后完成，当前 requirements.in 为骨架依赖范围。

静态目录只公开 web/assets，不公开照片、模型或配置。`live` 仅报告 API 存活，不能用于证明识别功能可用。

## Git 节奏

按用户要求，每个小任务完成并验证后单独 commit；每个阶段完成并验收后 push 一次。计划与设计基线单独提交。未完成的验收项如实记录，不为提交而标记通过。
