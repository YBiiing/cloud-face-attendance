# 第二次作业：注册与照片更新恢复验证

2026-09-29，Windows + Docker Linux，MySQL 8.4。

- 修复：照片替换完成后，相同幂等键与相同内容返回原任务，即使旧照片已经失效。
- 修复：注册任务查询中断时保留任务凭证，提供继续查询按钮；刷新后恢复查询，失败后只需重新上传照片。
- 上传和查询期间锁定表单，避免请求内容与幂等键发生变化；HTTP 请求 30 秒超时后提供重试提示。
- 不持久保存密码。若首次上传已被服务器接收，但浏览器尚未收到任务凭证就被关闭，此时不能自动恢复；上传网络异常时应保留原页面与原表单重试。

执行：

```powershell
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml run --rm --no-deps -v E:/A-project/cloud-face-attendance/tests:/srv/app/tests:ro tests python -m pytest tests/integration/test_week2_flow.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe tests/browser/check_registration.py
```

结果：业务流程测试 1 passed；浏览器回归 PASS。业务流程使用真实 HTTP 处理、图片解码、MySQL、worker 处理函数、事务与登录会话，仅替换测试进程内的特征提取器；浏览器恢复测试使用明确的接口测试数据。二者均不能证明真人识别准确率或真实手机相机兼容性。

首次新增测试误要求任务状态也完全一致；异步任务从 PENDING 到 SUCCEEDED 是合法变化，已改为校验任务 ID、凭证和查询 URL 不变，并明确断言重放结果为 SUCCEEDED。镜像落后于已有迁移导致的一次启动失败，已通过重建镜像解决。
