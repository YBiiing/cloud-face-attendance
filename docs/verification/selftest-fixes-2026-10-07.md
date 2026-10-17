# 自测问题修复记录

日期：2026-10-07。修复范围为前次自测列出的 7 项问题，并补充跨账号重复人脸录入与模拟器内存配置。开发与验证均在本地，云部署仍未进行。

## 修改内容

| 问题 | 处理 |
|---|---|
| 认证照片上传连接池相互等待 | 鉴权返回脱离 Session 的资料快照并释放连接；照片事务重新核验操作人员状态和权限；维持 5+5 连接池 |
| 老师无匿名签到链接入口 | 场次卡片增加打开、复制入口；自动复制不可用时显示可手动复制的链接 |
| 手机终态反馈落在屏幕外 | 注册、签到、照片库终态反馈滚动至可见位置，保留状态播报 |
| 更换照片仍显示旧成功 | 相册/相机 input 事件显示“照片已更换，请提交”，更换请求键，保留处理中任务恢复逻辑 |
| Redis/MySQL 故障等待较长 | 前台 Redis 1 秒超时、0 自动重试；MySQL 连接/池等待 1 秒、读写 2 秒；就绪检查独立池、1 秒读写；DNS 解析单次等待 250 ms、每主机名共享一个任务、两个线程上限 |
| 数据库不可用返回 500 | 连接中断和池超时统一 503；程序/SQL 错误继续 500，不暴露 SQL 或凭据 |
| 共用出口 30 次限流 | 默认来源 IP 600 次/分钟、场次预算 max(60,名单人数×3)，预算可配置；保留 50 个在途任务上限，429 带 Retry-After |
| 同一脸录入不同账号 | 在图库锁内检查其他有效账号；重复拒绝 FACE_ALREADY_ENROLLED，保持注册 PENDING 或旧照片有效 |
| 2 GB 模拟器相机返回失败 | E 盘启动入口与 AVD 配置统一为 3 GB；物理摄像头/真人验收仍待人工进行 |

## 验证结果

- 最终后端完整回归：**72 passed、2 warnings，24.19 秒**；包含连接池、权限、503、限流提示、重复人脸原子性、DNS 等待及 TLS 原主机名保留回归。两项警告为依赖弃用提示，没有关闭安全校验。
- 原有三引擎界面回归 11 组、新增三引擎移动反馈/复制入口回归 3 组通过。
- 独立连接池脚本：10×202，无异常，夹具清理完成；[pool-results.json](selftest-fixes-2026-10-07/pool-results.json)。
- 真实 HTTP 共享队列：注册 10×202/10×429、照片库 20×202、签到 20×202/10×503；50 个任务全部 NO_FACE，容量归零，拒绝请求未遗留照片，夹具清理完成；[queue-results.json](selftest-fixes-2026-10-07/queue-results.json)。
- 同来源 IP：同一场次 60 次接收，第 31 次不再误限流，第 61 次达到单人场次的 60 次最低预算，返回 429/RATE_LIMITED 与 Retry-After；[nat-results.json](selftest-fixes-2026-10-07/nat-results.json)。未伪造代理头或关闭限流，真实模型 60×NO_FACE，夹具清理完成。
- 真实模型闭环：ENROLLED、换图 CHECKED_IN、UNKNOWN_PERSON、NOT_IN_ROSTER、多场次和 10 并发 1 次新签到/9 次已签到均通过；[model-results.json](selftest-fixes-2026-10-07/model-results.json)。仅使用完全虚构合成人像，阈值 0.5、margin 0.05 未调整，夹具清理完成。
- 真实模型重复录入：换角度的 A 不能注册为另一账号，重复账号保持无法登录；A 可增加本人第二张照片；B 用 A 的脸替换时被拒绝且旧图仍可访问；[duplicate-results.json](selftest-fixes-2026-10-07/duplicate-results.json)。夹具清理完成。
- 真实依赖故障：Redis 不可用时 live 200、ready 503/281.8 ms、提交 503/255.5 ms；MySQL 不可用时 live 200、ready 503/4.7 ms、班级查询 503/1264.5 ms，恢复均 ready 200；[outage-results.json](selftest-fixes-2026-10-07/outage-results.json)。只停止隔离测试服务，开发项目未做故障注入。
- Docker Desktop 曾在中途退出，使用官方 CLI 恢复后继续验证；最初仅修改 socket 超时的尝试仍出现 8 秒 DNS 等待，未将该次算通过，随后定位并补齐了有界解析。
- 本地开发 API、worker、scheduler 已使用最终镜像重建启动，`http://192.168.31.29:8000/api/health/ready` 返回 ready，MySQL/Redis/model_worker 均为 ok；没有部署云服务。

界面证据：[老师复制链接降级](selftest-fixes-2026-10-07/chromium-teacher-links.png)、[320 像素屏幕的终态反馈](selftest-fixes-2026-10-07/chromium-feedback.png)。截图使用明确的 API 夹具，不作为真人签到截图。

实际手机拍摄、本人同意的真人样本准确率、真实 iPhone Safari 和云上持续吞吐仍属于原有待验收范围，未用合成图片替代。

收尾确认隔离测试库的活动任务、有效测试人脸、容量保留均为 0，随后停止测试项目，保留已更新的开发项目。临时目录 `.tmp/fix-20261007` 位于仓库内且证据已复制，使用准确绝对路径删除仍被自动审批以 `blocked by policy` 拒绝；未提供具体原因，因此保留 Git 忽略目录，没有改用其他方式绕过。

复制原有自测报告作为历史证据时没有将修复前的失败改写为通过。Git 提交/推送尚未执行，用户原有 api-contract.md 改动保留。
