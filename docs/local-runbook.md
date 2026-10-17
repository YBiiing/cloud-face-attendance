# 本地运行手册

第二次作业的完整启动、手机访问与截图顺序见 [第二次作业演示说明](week2-submission.md)。

## 容器启动（P1-02 起）

Windows 上先启动 Docker Desktop 并使用 Linux 引擎。所有命令在仓库根目录运行：

若启动日志明确显示 `dockerInference` 或 `engine.sock` 的 `The file cannot be accessed by the system`，先执行 `docker desktop stop --timeout 30` 并确认退出，然后运行 `./scripts/repair-docker-start.ps1`。脚本仅处理两处运行目录中的已识别零字节通信文件（含 `userAnalyticsOtlpHttp.sock`），将目录改名备份后启动 Docker；遇到其他内容或仍有后台进程会停止。可先加 `-WhatIf` 预览。镜像、数据库、命名卷与 WSL 磁盘不在操作范围内；备份保留，不自动删除。这是针对 [Docker Windows 残留套接字问题](https://github.com/docker/desktop-feedback/issues/460) 的恢复办法，不能保证上游问题不再复发。

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

停止时保留命名卷，不使用删除卷的命令。数据库和照片必须成套备份。启动时先执行 migrate 服务，成功后启动 API。模型与迁移检查：

```powershell
docker compose exec -T api alembic check
docker compose exec -T api python -m scripts.check_database
```

数据库检查脚本的临时写入全部回滚。新增数据库结构必须新增迁移，不修改已经应用的迁移。当前应用与迁移共用仅限本项目数据库的开发账号，生产环境另行分权。

## P1-01 历史骨架验证

P1-01 曾通过下面的 Windows 虚拟环境验证纯 HTTP 骨架。P1-02 起应用要求完整环境配置，请优先使用上面的容器启动方式；旧命令不能代替当前启动流程，也不代表模型容器兼容性已验证。

在 PowerShell 中运行：

```powershell
Set-Location E:\A-project\cloud-face-attendance
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.in
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

访问 `http://127.0.0.1:8000/`，存活检查为 `/api/health/live`。公开的 Swagger 与 OpenAPI 地址已关闭，开发时查阅仓库中的 `docs/api-contract.md`。按 Ctrl+C 停止；不删除数据。依赖版本见 requirements.lock。

静态目录只公开 web/assets，不公开照片、模型或配置。`live` 仅报告 API 存活，不能用于证明识别功能可用。

## 电脑端拍照与手机选图

电脑端请打开 `http://localhost:8000/`（服务器运行在本机时），点击“拍照”后允许浏览器摄像头权限：实时取景 → 拍摄 → 检查预览 → 使用这张照片 → 提交表单。拍摄和确认本身不上传。取消、Esc、重拍或离开页面会释放摄像头。单独的“选择照片文件”入口才打开文件选择器。

普通局域网 HTTP 地址不能调用电脑浏览器实时摄像头，会显示原因和操作指引。远程实时拍照需要 HTTPS；本机调试可以使用上述 localhost 地址。`compose.lan.yaml` 同时发布本机回环和指定局域网地址，保留手机访问。手机上的“拍照”继续使用系统原生拍摄入口，“从相册选择”单独选图。

若权限未允许、未检测到摄像头或摄像头被占用，页面显示中文原因，可重试或取消后选择文件。自动化验证使用浏览器原生虚拟视频设备，不能代替实体摄像头与本人照片的最终验收。详见 [电脑端实际测试](verification/desktop-camera-2026-10-07.md)。

## Git 节奏

按用户要求，每个小任务完成并验证后单独 commit；每个阶段完成并验收后 push 一次。计划与设计基线单独提交。未完成的验收项如实记录，不为提交而标记通过。

## 隔离测试

数据库迁移 `0008` 为班级名称增加唯一约束。若已有同名班级，迁移会在修改表结构前停止。请先核对这些班级的 ID、人员和历史场次，再分别设置不同名称后重试；不要删除或合并有人员、场次的班级。数据库按现有 MySQL 排序规则判重，大小写差异不能用来区分班级。仅用于本地验证的空测试班级可以在核实归属后清理。

服务器为页面中的静态资源添加按内容生成的版本路径；相对导入的 JavaScript 模块使用相同版本目录。更新镜像后重新打开或刷新页面即可加载新版本，已打开页面中的进行中操作不会被自动刷新。

```powershell
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml build tests migrate
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml run --rm --no-deps tests python -m scripts.prepare_models
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml run --rm tests
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml stop
```

必须同时使用项目名和覆盖文件；不要手动指向开发库。测试使用独立卷、face_attendance_test 数据库，不发布网络端口。常规测试只回滚本次数据。

完整 pytest 回归要求使用没有人工验收数据的独立测试项目（例如将以上命令的项目名改成 `face-attendance-test-regression`）。已有验收照片时不要清空图库；不同模型版本的自动化特征及整库备份用例会与它们冲突。执行 pytest 前停止这个项目的 `scheduler`，保留 `worker`，恢复相关用例会自行调用调度逻辑，避免外部调度器提前领取故障注入任务。运行真实网页和故障测试时可恢复 scheduler。

`tests/browser/check_live_attendance.py`、`check_desktop_camera.py`、`check_desktop_biometrics.py` 及 `scripts/load_test.py`、`scripts/test_redis_recovery.py` 支持 `ATTENDANCE_TEST_PROJECT`，仅允许 `face-attendance-test` 或以 `face-attendance-test-` 开头的隔离项目名。网页端点仍固定为回环地址 `127.0.0.1:8001`，同时使用 `compose.e2e.yaml`；先停止其他占用该端口的测试 API。前三个网页脚本支持 `ATTENDANCE_TEST_OUTPUT` 指定本轮证据目录，避免覆盖历史截图。

`/api/health/live` 检查 API；`/api/health/ready` 检查依赖。模型 worker 尚未就绪或心跳过期时 ready 返回 503，并将 model_worker 标记为 unavailable。响应 X-Request-ID 可关联日志；日志仅记录路由名、方法、状态与耗时，不记录请求体、查询参数或凭据。

## 模型准备

照片清理、备份恢复和故障验证见 [本地维护手册](local-maintenance.md)，本轮结果见 [P6 验证记录](verification/p6-local.md)。

运行 `docker compose run --rm --no-deps api python -m scripts.prepare_models` 下载官方研究模型，再运行 `docker compose run --rm --no-deps api python -m scripts.check_model` 检查。权重仅存模型卷，运行服务时不下载。若容器无法联网，可在宿主机运行 `python -m scripts.prepare_models`，再用 `docker compose cp models/buffalo_l api:/srv/models/` 复制到项目模型卷。下载需要网络与磁盘空间，失败后重试准备命令。

requirements.lock 来自 Linux Python 3.11 首轮真实安装，Docker 按锁文件安装；更新依赖须重新验证与生成锁文件。模型仅限非商业研究，原始照片与权重不提交。
