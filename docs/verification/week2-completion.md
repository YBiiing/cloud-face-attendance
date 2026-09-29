# 第二次作业编码验收记录

日期：2026-09-29。范围：本地手机 H5 + FastAPI + MySQL；云部署、匿名签到及签到记录的第三次作业验收不在本记录范围。

## 已完成代码

- 基本信息、班级、密码、标准照注册；任务查询与失败后重新上传。
- 服务器图片校验，真实人脸检测、对齐、512 维编码；异步入库成功后激活账号。
- 登录、退出登录、会话撤销、CSRF 防护与照片访问权限。
- 手机适配页面、文件选择器拍照入口、预览、上传与处理反馈。
- 登录后照片新增、替换、删除；幂等重放及注册查询中断恢复。
- 指定网卡的局域网 Compose 配置、只读 MySQL 证据查询工具和演示手册。

## 实际验证

| 验证 | 本次结果 | 证明范围 |
| --- | --- | --- |
| 隔离 MySQL 测试套件 | 28 passed，2 warnings | 含当前工作区既有场次/P5 提交接口测试；不代表 P5 功能已完成 |
| 新增注册到退出登录流程 | 1 passed | 真实图片解码、worker 业务处理、MySQL 事务、会话；仅特征提取为测试替身 |
| 增补数据库取证断言后复测 | 1 passed | ACTIVE、2048 字节特征、登录会话 1 → 0、无账号结果；未输出凭证字段 |
| Edge 浏览器回归 | PASS | 390×844 视口，查询中断恢复、任务刷新恢复、只重传照片；该专项使用接口测试数据 |
| Edge 连接本地真实 API | PASS | 班级加载、临时管理员登录、退出登录、退出后 /me 返回 401，无页面 JS 错误 |
| /api/health/ready | ready | MySQL、Redis、model_worker 均为 ok |
| scripts.check_model | PASS | 两个模型均为 CPUExecutionProvider，版本 buffalo_l:6c8808d2fac7336c:align-v1，载入约 2.787 秒 |
| alembic check | No new upgrade operations detected | 当前工作区模型与开发数据库结构一致 |
| Compose LAN 配置 | config --quiet 成功 | 配置解析，尚未从真实手机连接 |
| scripts.week2_snapshot | 成功 | 开发库不存在学号返回 account_found=false；存在账号的状态见隔离测试 |

两条警告分别来自 Starlette TestClient 的 httpx 迁移提示，以及 InsightFace 使用的 skimage estimate 弃用提示；未关闭检查或隐藏警告。模型载入时间只说明本机单次启动情况，不代表并发容量或识别准确率。

主要命令：

```powershell
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml run --rm --no-deps -v E:/A-project/cloud-face-attendance/tests:/srv/app/tests:ro tests python -m pytest -q -p no:cacheprovider
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml run --rm --no-deps -v E:/A-project/cloud-face-attendance/tests:/srv/app/tests:ro -v E:/A-project/cloud-face-attendance/scripts:/srv/app/scripts:ro tests python -m pytest tests/integration/test_week2_flow.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe tests/browser/check_registration.py
docker compose run --rm --no-deps api python -m scripts.check_model
docker compose exec -T api alembic check
```

测试前已构建对应镜像并启动隔离测试 MySQL、Redis、worker 和 scheduler。独立环境完整操作见 [演示手册](../week2-submission.md)。

## 截图与清理

- [注册页](week2-register.png)：真实本地页面，手机宽度视口。
- [登录成功](week2-login-fixture.png)：临时管理员测试账号，不能当作真人注册成功证据。
- [退出登录](week2-logout.png)：真实会话撤销后的页面。
- 较早的真实无脸拒绝页面见 [注册拒绝](p3-registration-rejected.png)。

已核对本次截图，未出现裁切和横向溢出。开发库中此前为页面测试创建的临时管理员、临时学生、PENDING 账号、关联场次与上传文件已按确切 ID 和标记核对后清理；本地临时凭据文件也已删除。隔离测试服务已停止并保留卷，开发服务继续监听 127.0.0.1:8000，停止命令为 `docker compose stop`。

## 尚需真人与手机完成的提交材料

当前没有自愿提供的本人照片，未实际验证真人成功录入与匹配效果；未控制真实手机相机。按照 [演示手册](../week2-submission.md) 完成本人注册、手机拍照、登录/退出、照片上传，再截取对应数据库变化，才能声明整份第二次作业提交材料齐全。

本次结论为：**第二次作业编码任务完成，真人和手机验收材料待补。**
