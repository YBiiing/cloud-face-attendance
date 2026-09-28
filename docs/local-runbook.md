# 本地运行手册

## 容器启动（P1-02 起）

Windows 上先启动 Docker Desktop 并使用 Linux 引擎。所有命令在仓库根目录运行：

```powershell
python scripts/init_env.py
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
```

初始化脚本仅在 `.env` 不存在时生成随机密钥，不覆盖已有文件，不输出密码。`.env.example` 列出可配置字段。不要分享完整 `docker compose config` 输出，它包含解析后的秘密；使用 `--quiet` 检查配置。

页面为 `http://127.0.0.1:8000/`，MySQL 仅在 `127.0.0.1:3307` 对开发工具开放，库名 face_attendance、用户名 attendance，密码来自本机 `.env`。Redis 不发布主机端口。现有宿主机 MySQL 不受影响。

```powershell
docker compose logs --tail 50 api
docker compose stop
docker compose start
```

停止时保留命名卷，不使用删除卷的命令。数据库和照片必须成套备份。P1-03 接入迁移后启动将先迁移再启动 API。

## P1-01 历史骨架验证

P1-01 曾通过下面的 Windows 虚拟环境验证纯 HTTP 骨架。P1-02 起应用要求完整环境配置，请优先使用上面的容器启动方式；旧命令不能代替当前启动流程，也不代表模型容器兼容性已验证。

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
