# 学生与老师使用流程调整

日期：2026-10-02。本轮根据实际操作反馈调整页面与接口，保留原有匿名人脸检索签到流程。

## 反馈处理

| 反馈 | 当前实现 |
| --- | --- |
| 学生自行查看需要签到的场次 | 登录后的学生工作台提供“待签到 / 全部场次”，展示本人名单内场次、时间与签到状态；进行中场次可直接进入签到 |
| 管理员称呼改为老师 | 用户页面、权限提示及账号创建命令统一称呼“老师”；内部 ADMIN 角色值保持兼容，不改已有账号和数据库 |
| 老师界面没有上传照片功能 | 老师工作台只提供创建签到、已创建签到、签到记录；直接打开学生照片页也会返回工作台 |
| 创建与已创建页面分开 | `/session-create.html` 创建签到及班级，`/sessions.html` 查看已发布场次；发布成功后跳转列表并提示成功 |
| 增加相册入口 | 注册、照片库、签到页面均提供“从相册选择”和独立“拍照”按钮；相册 input 不设置 capture，拍照 input 设置 capture=user |
| 改善交互 | 按角色导航、加载与空状态、文件名反馈、可见焦点、移动端单列、清晰操作按钮、错误与成功提示；老师创建页默认当前时间至 30 分钟后 |
| 区分登录前后页面 | 登录后跳转 `/dashboard.html`；已登录访问首页或登录页也进入工作台；退出后返回登录页；工作台不显示注册/登录入口 |
| 密码 6 位 | 注册、登录、老师账号创建统一允许 **6–128 位字符**，前后端一致。含义是最低 6 位，不强制所有密码必须恰好 6 位，旧密码继续有效 |

## 学生场次接口补充

`GET /api/sessions/mine?view=pending&page=1&page_size=20`

- 必须以学生身份登录；未登录 401，老师 403。
- `view=pending` 返回名单内尚未完成且未结束的场次，包括未来场次；`view=all` 包含已签到与已结束场次。
- 按已冻结的 `session_members` 查询，不允许通过客户端指定 user_id 查看别人的场次。学生后加入班级时，不会自动进入之前已发布的名单，需老师创建新场次。
- 列表包含场次标题、班级、时间、签到路径、`status` 和 `attendance_status`（PENDING / ATTENDED / MISSED），支持分页。
- 点击场次后仍仅提交照片与场次码。后端通过人脸库识别人，不把登录账号作为照片身份，也不要求签到提交必须登录。

老师账号管理权限的内部编码继续使用 ADMIN。移除老师页面的照片入口没有取消已有后端受控照片管理接口的授权语义，避免破坏已有接口兼容。

## 验证与截图

新增服务端验证覆盖名单隔离、未开始/进行中/关闭、已签到过滤、分页、权限及 5/6/128/129 位密码边界。新增浏览器脚本覆盖登录跳转、退出、学生发现并进入签到、老师无照片入口、创建与列表分离，以及两个选图入口。

```powershell
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml build tests migrate
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml run --rm tests
.\.venv\Scripts\python.exe tests/browser/check_registration.py
.\.venv\Scripts\python.exe tests/browser/check_attendance.py
.\.venv\Scripts\python.exe tests/browser/check_review_fixes.py
.\.venv\Scripts\python.exe tests/browser/check_hci_flow.py
```

初次完整测试因多个独立用例共用默认来源地址、累计登录超过限速而失败（62 passed / 1 failed）。测试客户端现使用独立模拟来源地址，同一测试内部仍共用地址；另加连续 21 次登录断言第 21 次被限流，未关闭或调高业务限流。

最终重新构建镜像并按上述常规命令运行：**64 passed，2 warnings，22.53 秒**。两条警告为已有 Starlette/httpx 与 InsightFace/skimage 弃用提示。四个浏览器脚本均通过。

页面截图来自 390×844 的隔离 Edge 与明确标注的测试数据，已检查无横向溢出：

- [登录](hci-2026-10-02/login.png)
- [学生工作台](hci-2026-10-02/student-dashboard.png)
- [拍照与相册入口](hci-2026-10-02/photo-options.png)
- [老师工作台](hci-2026-10-02/teacher-dashboard.png)
- [创建签到](hci-2026-10-02/teacher-create.png)
- [已创建签到](hci-2026-10-02/teacher-sessions.png)

浏览器脚本使用 mock API；拍照测试验证浏览器文件选择器和文件传递，不代表已经验证真实手机相机、相册格式兼容或真人识别。服务端测试使用独立 MySQL/Redis；未向开发库写入测试人员。真实手机与真人验收、云部署仍按原计划后续完成。
