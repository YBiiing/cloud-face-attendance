# 第三次作业：签到与记录演示说明

## 当前范围

本轮完成本地编码和自动化验证：管理员按班级创建限时签到，学生无需登录拍照上传，服务器检索全部有效人脸后核对名单；登录后查看签到记录。第二次作业的注册、登录、照片上传操作说明继续保留在 [第二次演示说明](week2-submission.md)。

用户已明确暂不提供照片。本人成功签到、未录入人员真人拒识、实际手机相机操作与对应提交截图留待后续。自动化测试中的合成特征不能替代真人识别验收，空白图片的 NO_FACE 也不等于未知人员的 UNKNOWN_PERSON。云部署仍最后进行。

## 一、启动与准备

从仓库根目录运行，初次配置、模型准备、管理员创建与手机局域网访问方式沿用第二次说明：

```powershell
Set-Location E:\A-project\cloud-face-attendance
docker compose up -d --build --wait
Invoke-RestMethod http://127.0.0.1:8000/api/health/ready
docker compose exec -T api alembic check
```

逐条确认成功；`ready` 中 mysql、redis、model_worker 均应为 ok。数据库迁移会新增任务场次关联和 attendance_records，不删除已有人员或照片。首页为 `http://127.0.0.1:8000/`。

为正式演示准备两个已同意使用照片的人：

- A：通过注册页面录入，等待成功激活，至少保留一张不同于标准照的新照片用于签到。
- B：不注册、不上传到照片库，使用 B 的清晰单人照片测试未知身份。
- 可选 C：在另一个班级注册，用于验证“人已录入，但不在当前名单”。

管理员需先建班级，再完成学生注册，最后创建签到。创建场次时会冻结该班已激活学生名单；之后新注册的人员不会自动加入旧场次，应创建新场次。

当前匹配配置为开发初值 `MATCH_THRESHOLD=0.5`、`MATCH_MARGIN=0.05`，尚未经真人样本校准。后续使用 `scripts/evaluate_faces.py` 的已录入与未知样本评估后再调整，不通过降低阈值强行制造成功。

## 二、主要演示顺序

### 1. 注册并录入信息

按照第二次说明完成 A 的姓名、学号、班级、密码和标准照片注册，看到成功后登录，打开照片库确认标准照可见。保存注册成功及对应数据库状态截图。

### 2. 创建一次课程签到

1. 管理员登录 → 课程签到管理。
2. 填写课程标题，选择 A 所在班级，设置开始、结束时间。
3. 发布场次，核对应到人数；复制该场次签到链接。
4. 手机另开未登录页面访问链接。用手机访问时，应从局域网地址的管理页面复制链接，不能把 `127.0.0.1` 发给手机。

### 3. 已录入人员签到

1. A 在有效时段内拍照或选择另一张本人照片，点击“上传并签到”。
2. 页面依次显示上传、排队/识别状态；仅终态成功显示“签到成功”。
3. 刷新页面只查询原任务，不再次上传。
4. 再次选择照片提交，应显示“本场次已签到”，服务器仍只有一条该人员该场次的记录。

签到请求只包含场次码、照片与幂等键；不通过登录 Cookie、学号或设备身份确定签到对象。

### 4. 未录入人员签到

1. B 使用同一场次链接提交清晰单人照片。
2. 预期显示“未识别到已录入人员”，无新增成功记录。
3. 多人照片、模糊或无人脸图片分别得到相应提示；这些是输入质量演示，应与未知人员演示分开。
4. 如果身份相似、无法明确，返回“身份无法明确”，不会任选一人写入。

### 5. 查看签到记录

- 管理员从场次卡片点击“查看名单与签到记录”，看到完整冻结名单，以及应到、已到、暂未到和处理中任务数。
- 普通用户登录 → 签到记录，只能看本人的成功记录。
- 管理员提前结束场次或等待截止后，新照片不能上传；截止前完整接收的任务仍可处理。
- 结束且没有有效未完成任务时，统计显示“本场结果已确定”。再次创建另一场次，A 可以再次签到，记录按场次分开。
- 退出登录后再次访问记录页，应提示先登录，不继续显示旧名单。

## 三、服务器数据库变化与截图

记录页面 URL 中 `session_id` 是场次编号，例如 `/records.html?session_id=12`。使用该编号查询只读证据：

```powershell
docker compose exec -T api python -m scripts.week3_snapshot --session-id 12
```

脚本直接读取 MySQL，输出该场次状态、人数、任务状态计数、最多 100 条成功记录和最近 20 个任务。不输出人脸向量、图片、密码或访问凭证；人数统计覆盖全部记录，不受展示条数限制。

| 操作 | 页面预期 | 数据库预期 |
| --- | --- | --- |
| 首次成功 | 签到成功 | SUCCEEDED/CHECKED_IN；新增一条 attendance_records |
| 同人再次提交 | 本场次已签到 | SUCCEEDED/ALREADY_CHECKED_IN；原记录和首次接收时间不变 |
| 未知人员 | 未识别到已录入人员 | REJECTED/UNKNOWN_PERSON；成功记录不增加 |
| 名单外已录入人员 | 不在本场次签到名单 | REJECTED/NOT_IN_ROSTER；成功记录不增加 |
| 无人脸图片 | 未检测到人脸 | REJECTED/NO_FACE；成功记录不增加 |
| 截止后新上传 | 场次已结束 | 不创建新任务、不写记录 |
| 排队容量已满 | 稍后再试 | 503/QUEUE_FULL；不遗留新任务和照片 |

建议正式提交截图：A 注册成功、A 首次签到成功、B 未识别反馈、管理员名单统计、普通用户个人记录，以及前后数据库查询结果。本人照片和含个人信息的截图放在 `private-samples/week3-evidence/`，按课程渠道提交，不推送 GitHub。

本仓库的 `week3-real-no-face.png`、`week3-live-records.png`、`week3-database-no-face.png` 是隔离环境自动化演示证据，使用临时测试账号和真实空白图片处理链，不是三项真人演示已经完成的证明。

## 四、接口与并发规则

| 接口 | 权限 | 说明 |
| --- | --- | --- |
| POST /api/checkins | 无需登录 | multipart：session_code、photo；Idempotency-Key 请求头；返回 202 与任务凭证 |
| GET /api/tasks/{id} | 任务凭证或管理员 | X-Task-Token；只反馈状态和结果码，不公开匹配到的姓名、学号 |
| GET /api/records/sessions | 登录 | 当前用户可见的场次列表，支持 page/page_size |
| GET /api/records | 登录 | session_id 可选、page/page_size；普通用户固定本人范围，管理员按场次显示名单统计 |

HTTP 入口限文件大小并按 IP 限速；Redis 原子限制最多 50 个未到期签到任务；Celery 预取 1、当前单 CPU worker，模型处理不阻塞 HTTP 请求线程。任务先存 MySQL，发送队列失败由 scheduler 补发。模型推理在数据库事务外，最终写入使用短事务、执行尝试校验与数据库唯一约束，避免重放和并发产生重复记录。

这些是已实现的并发控制措施。12 请求争用 5 个配额的测试只验证原子性；实际多人照片的吞吐、排队 P95 和云上容量尚未压测，不承诺具体并发性能。多人共用同一公网出口时 IP 限速可能影响体验，云部署前需要结合课堂网络进行校准。

## 五、复现自动化验证

```powershell
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml build tests migrate
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml run --rm --no-deps tests python -m scripts.prepare_models
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml run --rm tests
.\.venv\Scripts\python.exe tests/browser/check_registration.py
.\.venv\Scripts\python.exe tests/browser/check_attendance.py
```

浏览器专项要求宿主机虚拟环境已安装 playwright，且电脑有 Microsoft Edge。真实 API 联调额外启动**隔离测试库**的 API，仅绑定本机 8001：

```powershell
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml -f compose.e2e.yaml up -d --wait api worker scheduler
.\.venv\Scripts\python.exe tests/browser/check_live_attendance.py
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml -f compose.e2e.yaml --profile test-api stop
```

联调脚本拒绝连接非 test 数据库，只创建带随机标记的临时账号和场次；结束时按精确 ID 清理。脚本不会安装模型替身，也不会通过数据库伪造成功签到。截图来源及每项验证边界见 [本地功能验收记录](verification/local-functional.md)。

开发服务供继续演示保留，结束时运行 `docker compose stop`；保留数据卷，不使用删除卷命令。
