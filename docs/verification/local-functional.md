# 第三次作业本地功能验收记录

2026-09-29。结论：**第三次作业本地编码与自动化验证完成；真人照片、实际手机及云部署验收待补。** 用户明确选择暂不提供照片，先完成编码与自动化验证。

## 功能与证据

| 内容 | 实际结果 | 证据边界 |
| --- | --- | --- |
| 匿名签到接收、幂等、截止时间、队列满清理 | 通过 | 真实 MySQL/Redis；不接收客户端人员身份 |
| 两个任务并发签到同一人 | 仅一条成功记录 | 两线程事务验证，唯一约束与首次时间不变 |
| 不同场次、过期任务、旧尝试、库版本变化 | 通过 | 数据库事务和状态规则 |
| 注入事务失败 | 回滚记录与任务状态 | 没有部分成功 |
| 注册 A → 创建场次 → 匿名 A 签到 → 重复签到 → 未知 B → 查记录 | 通过 | 真 API/MySQL/业务处理；测试进程中替换特征提取器，不证明真人识别准确率 |
| 未知、相似身份与名单外人员 | 返回对应拒绝码且无成功记录 | 合成单位向量验证匹配与名单规则 |
| 普通用户隔离、管理员跨页统计、结束后最终状态 | 通过 | 数据库/HTTP 断言，退出后 401 |
| 12 线程竞争 5 个 Redis 配额 | 仅 5 个接收，释放后可补入 | 原子性验证，不是推理吞吐压测 |
| 浏览器注册恢复专项 | PASS | 测试接口数据，390×844 Edge 视口 |
| 浏览器签到和记录专项 | PASS | 测试接口数据；无 Cookie 上传、刷新恢复、A/B 场次隔离、未知提示、退出后清除记录 |
| 浏览器 → 真 API → Celery → ONNX | PASS，NO_FACE | 空白 PNG 真实拒绝，未使用模型替身 |
| 真实记录页与 MySQL 证据查询 | 一致 | 应到 1、已到 0、暂未到 1；1 个 REJECTED/NO_FACE，刷新未增加任务 |

整套隔离测试最终结果：**35 passed，2 warnings，9.28 秒**。两条警告分别为 Starlette TestClient 的 httpx 迁移提示和 InsightFace 使用 skimage estimate 的弃用提示，未屏蔽。此前 34 项回归已通过，随后增加了完整课程演示业务测试和数据库证据断言，最终重新运行整套测试。

## 执行命令

运行时镜像已重建，测试使用 face-attendance-test 独立项目、数据库及卷。开发库未用于合成特征测试。

```powershell
docker compose build api
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml -f compose.e2e.yaml up -d --wait api worker scheduler
.\.venv\Scripts\python.exe tests/browser/check_live_attendance.py
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml run --rm --no-deps -v E:/A-project/cloud-face-attendance/app:/srv/app/app:ro -v E:/A-project/cloud-face-attendance/scripts:/srv/app/scripts:ro -v E:/A-project/cloud-face-attendance/tests:/srv/app/tests:ro tests python -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe tests/browser/check_registration.py
.\.venv\Scripts\python.exe tests/browser/check_attendance.py
```

新环境从构建、模型准备开始的完整命令见 [第三次演示说明](../week3-submission.md)。第二次演示说明保留在 [原文件](../week2-submission.md)，未被第三次文档覆盖。

## 本次实际截图

- [匿名上传经真实模型拒绝](week3-real-no-face.png)。
- [登录后管理员查看名单](week3-live-records.png)。
- [MySQL 只读查询结果](week3-database-no-face.png)：由真实查询 JSON 排版后截图，非数据库客户端截图。

截图已逐张查看，手机宽度页面无横向溢出。临时账号明确标为自动化测试，学生没有录入照片；截图不能用于宣称真人成功签到或未知人员拒识。浏览器联调脚本结束后已清理其确切 ID 的账号、场次、任务、会话、图片和配额；保留正式截图与代码。

## 环境恢复记录

恢复测试时 Docker Desktop 曾因 `%LOCALAPPDATA%/docker-secrets-engine/engine.sock` 无法访问而启动失败，导致未完成的联调命令中断。日志与 [Docker 官方问题区的报告](https://github.com/docker/for-win/issues/15064) 相符。

核实该目录只有一个 0 字节运行时套接字后，停止本次已崩溃的 Docker 进程，将该目录改名为 `docker-secrets-engine.cloud-face-backup-20260929171147`，重新启动 Docker，随后真实联调与完整测试均通过。该备份保留用于恢复；未删除容器卷、数据库、模型、照片或凭据，也未恢复出厂设置。

## 保留的验收项

1. 本人同意的真人标准照与另一张签到照，验证注册及成功签到。
2. 未录入人员真人照，验证 UNKNOWN_PERSON；无脸图片不能替代。
3. 实际手机相机、同一局域网访问与对应提交截图。
4. 按实际样本校准匹配阈值；当前 0.5 / 0.05 为开发初值。
5. 多人照片吞吐、P95、故障恢复强化及云端公网部署，按后续 P6/部署阶段实施。

本次未将 P5-05 的真人演示验收标记为通过，未开始云部署。
