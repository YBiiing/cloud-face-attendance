# 本地完整回归与 Docker 恢复（2026-10-17）

## 结论

本轮后端全量回归 **75 passed、2 warnings、25.16 秒**。真实网页、虚拟摄像头、合成人像识别、队列容量与依赖中断恢复均完成验证。未进行安卓、云部署或真人准确率验收。机器可读结果见 [summary.json](full-regression-2026-10-17/summary.json)。

## 环境与隔离

- Windows，Docker Engine 29.2.1，容器 Python 3.11.16；真实 MySQL、Redis、Celery、CPU ONNX，模型 `buffalo_l:6c8808d2fac7336c:align-v1`。单 worker、单推理线程，匹配阈值 0.5、margin 0.05，未修改阈值或关闭限流。
- 新建 `face-attendance-test-final` 项目，独立数据库、照片和 Redis 卷，模型从现有测试模型卷复制；数据库名仍为受保护的 `face_attendance_test`。网页仅发布 `127.0.0.1:8001`，原测试项目暂时停止。
- 全套 pytest 执行前停止独立 scheduler，保留 worker。故障恢复用例自行调用调度逻辑；网页、负载和依赖恢复测试时恢复 scheduler。
- 原有网页验收库保留 5 用户、4 班级、11 张有效合成照片和 1 条签到记录，前后计数一致。新项目的用户、班级、有效照片、签到记录、活动任务与容量均清零，见 [清理结果](full-regression-2026-10-17/cleanup.json) 和 [原库恢复核对](full-regression-2026-10-17/original-restored.json)。

## 验证结果

| 范围 | 实际结果与证据 |
|---|---|
| 后端全量 | 75 项通过，含权限、幂等、连接池、重复录入、班级唯一性、并发事务、存储、备份、任务租约及进程崩溃恢复；[原始输出](full-regression-2026-10-17/pytest-final.txt) |
| 浏览器界面夹具 | 16 次脚本运行通过：注册恢复、审查回归、签到流程各 1 次；HCI 在 10 种尺寸下通过；反馈、换图、复制降级在 Chromium/Edge、Firefox、WebKit 下各通过 1 次。接口响应为夹具，不能作为真实识别证据 |
| 尺寸覆盖 | 320×568、360×800、390×844、412×915、430×932、768×1024、844×390、1024×768、1366×768、1920×1080；检查布局、导航、表单和横向溢出。这是浏览器尺寸模拟，不等于实体手机验收 |
| 真实摄像头链路 | 有窗口 Edge、原生虚拟视频设备，23 项通过（含精确清理）：取景、取消、Esc、重拍、确认 JPEG、三处真实上传与 ONNX 无脸拒绝、轨道释放、权限拒绝与重试、5 种弹窗尺寸，拍照不触发文件选择；[结果](full-regression-2026-10-17/camera/results.json) |
| 环境限制 | 4 项通过：零摄像头设备提示及重试、实际局域网 HTTP 中文说明、localhost 安全上下文、不触发文件选择或写开发数据；[结果](full-regression-2026-10-17/camera-environment/environment-results.json) |
| 真实识别闭环 | 两个完全虚构的合成人像，实际页面注册、不同照片匿名签到、重复签到、未知人员拒绝、冻结名单拒绝、同日不同场次与记录查询通过。数据库共 4 条成功记录；特征为归一化 512 维向量；[结果](full-regression-2026-10-17/biometrics/ai-face-results.json) |
| 实际人工式网页操作 | 另通过浏览器控制直接检查：无效场次不保留加载文字且不显示上传表单；匿名访问记录跳转登录；320 像素宽下错误账号反馈明确且无横向溢出。该次截图工具超时，未声称保存了截图 |
| 数据库与源码一致性 | 原测试库、开发库 `alembic check` 均无结构漂移，迁移为 0008；运行中的两个 API 的 87 个应用、网页和迁移文件与工作区 SHA256 一致；[源码核对](full-regression-2026-10-17/source-match.json) |
| 语法 | 119 个 Python 文件 AST 解析、14 个 JavaScript 文件 `node --check` 通过 |

两项 pytest 警告分别来自 Starlette/httpx 与 insightface/scikit-image 的弃用提示；未屏蔽警告或降低断言。

## 并发与恢复

1. **真实人脸模型的同身份重复并发**：图库 2 个合成身份，10 个客户端同时上传同一张约 1.93 MB 的照片，结果为 1 次 CHECKED_IN、9 次 ALREADY_CHECKED_IN。接收 P95 **589.8 ms**，端到端 P95 **2855.1 ms**，未产生重复签到记录。这不能代表 10 个不同真人同时签到的吞吐。
2. **真实无脸负载**：图库为空，640×640 PNG，2566 字节，1/5/10/20 并发各一轮，共 36 次请求全部 202→NO_FACE。20 并发时接收 P95 **451.2 ms**、端到端 P95 **2328.67 ms**；所有轮次排队 P95 **2168.09 ms**、处理 P95 **145.13 ms**。[原始数据](full-regression-2026-10-17/load.json)。这些是短时无脸拒绝数据，没有测持续吞吐与 CPU/内存峰值。
3. **容量边界**：暂停本项目 worker 与 scheduler，使用 10 个并发客户端发出 60 次有效空白图片请求；50 次接收，10 次返回 503/QUEUE_FULL。在途容量保持 50，拒绝请求不新增任务。恢复服务后约 **9.85 秒**处理完 50×NO_FACE，容量归零并清理夹具。[结果](full-regression-2026-10-17/queue-results.json)，[本轮探针源码](full-regression-2026-10-17/queue_probe.py)。执行该探针必须在仓库根目录设置 `ATTENDANCE_TEST_PROJECT=face-attendance-test-final`，并使用配套隔离 Compose 项目和 8001 回环端点。
4. **依赖中断**：Redis 停止后 live 200，ready 503/1280.0 ms，提交 503/1255.9 ms；MySQL 停止后 live 200，ready 503/15.5 ms，班级查询 503/1262.0 ms。恢复后均 ready 200。[结果](full-regression-2026-10-17/outage-results.json)。另单独验证 Redis 发布失败、数据库扫描补投、真实 Celery 成功，尝试次数为 1。

## 失败尝试与修正

- 最初复用了含 11 张验收照片的测试库：70 通过、5 失败。自动化特征与已有模型版本冲突，整库备份也包含额外照片。未删除原图库，改用全新独立项目。
- 新项目第一次重跑 74 通过、1 失败：外部 scheduler 抢先领取了子进程崩溃测试的任务。停止该 scheduler 后整套 75 项通过；没有弱化崩溃断言。
- 合成人像网页闭环首次运行到并发脚本时返回 422/INVALID_REQUEST。定位为 Windows 系统代理接管 urllib 的回环请求，导致 multipart 上传没有照片字段。固定回环端点的测试使用独立无代理 opener 后，完整闭环及 10 并发通过；未修改服务端请求校验。
- 一项历史浏览器断言仍等待记录页内显示失效提示，但新行为会跳转登录；更新为断言跳转、登录表单可见及受保护内容消失，重跑通过。
- Firefox/WebKit 首次启动未找到默认缓存中的二进制，设置已有 `E:\Mobile-Emulators\WebTests\Browsers` 目录后运行通过，没有重复安装。

## Docker 启动恢复

本机日志依次在 `dockerInference` 和 `engine.sock` 报 `The file cannot be accessed by the system`。文件是零字节 ReparsePoint，单文件改名失败；直接删除命令曾被自动审批拦截且未执行。已按 [Docker 官方仓库同类问题](https://github.com/docker/desktop-feedback/issues/460) 中的目录保留办法恢复：停止 Docker，仅将已识别通信文件所在运行目录改名备份，再启动。

提供 [repair-docker-start.ps1](../../scripts/repair-docker-start.ps1)：先验证 Docker 已退出、目录不是链接且仅含白名单通信文件，再执行改名保留。第一次试运行遇到额外 `userAnalyticsOtlpHttp.sock` 时按设计停止；检查确认为本版本创建的零字节通信文件后补入白名单。`-WhatIf` 预览和脚本实际执行均通过，启动及 `docker info` 均退出 0，引擎为 29.2.1。镜像、数据库、命名卷、WSL 磁盘和设置未重置，备份目录保留。此脚本是恢复办法，不代表已经修复 Docker 上游缺陷。

结束时恢复原测试服务与开发服务。`127.0.0.1:8000`、`127.0.0.1:8001`、本机局域网 `192.168.31.29:8000` 的 ready 均为 200，MySQL、Redis、model_worker 均为 ok；[结果](full-regression-2026-10-17/health.json)。临时完整回归项目已停止。停止保留的服务可运行对应 Compose 项目的 `stop`，不删除数据卷。

## 尚未验收的范围

本人同意的真人照片准确率与阈值校准、实体手机/摄像头、真实 iPhone Safari，以及云上部署和持续多用户吞吐仍待后续验收。WebKit 桌面引擎和合成人像不替代这些结论。安卓按用户本轮指示排除。
