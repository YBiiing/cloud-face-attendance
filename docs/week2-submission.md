# 第二次作业：本地演示与提交说明

## 1. 当前交付范围

第二次作业的编码目标：手机 H5 与服务器连通，支持基本信息和标准照注册、登录、退出登录、拍照选择与上传。照片库只能登录访问。当前已实现这些接口和页面，使用 MySQL 保存资料和任务、Redis/Celery 异步处理照片、真实 ONNX 模型进行检测与编码。

本次完成的是**编码与自动化验证**。完整作业提交还需要使用自愿提供的本人照片进行成功录入、在实际手机上操作，并补充相应页面和数据库变化截图。现有电脑浏览器截图、测试替身产生的成功结果均不替代这些证据。云端部署在后续阶段进行。

“注销”在本阶段指退出登录并撤销会话，不是删除账号。第三次作业的匿名签到及签到记录不属于本次完成声明。

## 2. 启动电脑端服务

在 PowerShell 中进入仓库，启动 Docker Desktop 的 Linux 引擎后执行：

```powershell
Set-Location E:\A-project\cloud-face-attendance
python scripts/init_env.py
docker compose config --quiet
docker compose build api
docker compose run --rm --no-deps api python -m scripts.prepare_models
docker compose run --rm --no-deps api python -m scripts.check_model
docker compose up -d --wait
Invoke-RestMethod http://127.0.0.1:8000/api/health/ready
```

逐条执行；上一条失败时先处理原因。模型下载有网络要求，已有完整模型时准备脚本复用文件。下载失败的宿主机复制方案见 [本地运行手册](local-runbook.md)。`ready` 必须显示 MySQL、Redis 和模型 worker 均为 `ok`；首次模型加载需要等待，API 存活不等于模型已就绪。

首页：`http://127.0.0.1:8000/`；接口说明：`http://127.0.0.1:8000/api/docs`。

首次使用需建立管理员（不会自动提供默认密码）：

```powershell
docker compose exec api python -m scripts.create_admin
```

按提示填写管理员账号、姓名和密码。管理员用于创建班级，不通过此命令录入学生照片。登录页面登录管理员，在“管理课程签到”页面的“创建班级”区域添加班级。随后退出管理员，开始学生注册演示。

## 3. 手机通过同一局域网访问

手机和电脑连接同一可信 Wi-Fi，查看电脑当前网卡地址：

```powershell
Get-NetIPConfiguration
```

选择 Wi-Fi/以太网的局域网 IPv4，不选 Docker、VPN 或回环地址。将下面示例 IP 改为实际地址：

```powershell
$env:LAN_BIND_IP = '192.168.1.100'
docker compose -f compose.yaml -f compose.lan.yaml config --quiet
docker compose -f compose.yaml -f compose.lan.yaml up -d --wait
```

手机访问 `http://192.168.1.100:8000/`（替换实际 IP）。此配置只向指定网卡开放 API；MySQL 仍只绑定电脑回环地址，Redis 不开放端口。电脑浏览器也改用该局域网地址。Windows 防火墙如阻止连接，只给可信专用网络放行 TCP 8000；不关闭防火墙。校园网络若禁止设备互访，可改用双方连接同一手机热点的方式实测。

照片输入通过浏览器文件选择器请求前置拍照。相机、相册选项受手机系统影响；如果不能直接调用相机，先用系统相机拍照，再选择 JPEG/PNG 文件。页面不依赖在 HTTP 下不可用的实时摄像头 API。尚未声称任一具体手机型号已通过验证。

恢复仅电脑访问：

```powershell
docker compose up -d --wait
Remove-Item Env:LAN_BIND_IP
```

## 4. 实际演示和截图顺序

请使用本人自愿提供的单人、清晰、正面照片，最大 8 MiB。可以用同一账号按下表完成演示，避免用不同账户的截图拼接状态。

| 步骤 | 手机页面操作与截图 | 数据库应出现的变化 |
| --- | --- | --- |
| 注册前 | 注册页选择班级，填写姓名、学号、密码，拍照并预览 | 指定学号不存在 |
| 注册提交 | 点击提交，看到排队/处理中 | users.status=PENDING，任务为 PENDING/RUNNING；处理快时可直接观察最终状态 |
| 录入成功 | 显示“注册成功，可以登录了” | users.status=ACTIVE；ENROLL 任务 SUCCEEDED/ENROLLED；有效 face_samples 为 512 维、2048 字节 |
| 登录 | 输入刚注册的账号密码，显示已登录 | login_sessions 新增有效会话 |
| 上传 | 登录后打开照片库，新增或替换标准照，等待成功 | FACE 任务成功；新增有效标准照；替换时旧照 DISABLED |
| 退出登录 | 点击退出登录，显示“已退出登录” | 当前登录会话撤销；未登录再访问照片库返回 401 |
| 非人脸反馈 | 用另一测试学号提交无脸图片 | NO_FACE、REJECTED，用户保留 PENDING，不能登录；页面可重新上传照片 |

录入失败不会激活账号。保留注册页面，按提示更换照片；查询网络中断后点“继续查询注册结果”。若首次上传响应丢失，保持原页面和字段不变重试，服务器会按幂等键返回原任务。首次响应到达前关闭页面会丢失该请求的恢复信息，这种情况暂不提供账户找回功能。

### 安全查看数据库变化

每一步操作前后分别运行（将学号改为自己的演示账号）：

```powershell
docker compose exec -T api python -m scripts.week2_snapshot --student-no 你的演示学号
```

工具只读 MySQL，仅展示指定用户的基本信息、最近十个任务状态、照片维度及有效登录会话数量，不输出密码哈希、Cookie、任务凭证或人脸向量。对结果窗口截图即可展示服务器数据库状态。只有一次登录时，登录前后会话数量通常为 0 → 1 → 0；其他设备有未退出会话时总数可能更高。

若助教要求数据库客户端截图，连接 `127.0.0.1:3307`、数据库 `face_attendance`、用户 `attendance`，密码从本机 `.env` 读取。仅选取上述状态字段，不展示全表敏感字段。截图保存到本机私有目录 `private-samples/week2-evidence/`，按课程要求提交，不将本人照片和个人资料截图推送 GitHub。

建议材料：注册填写与照片预览、注册成功、登录成功、照片上传成功、退出登录，以及对应数据库操作前后截图。现有 [验证目录](verification/) 中的截图仅作为界面开发记录。

## 5. 自动化验证

测试使用独立的 face_attendance_test 数据库和卷，先准备测试模型：

```powershell
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml build tests migrate
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml run --rm --no-deps tests python -m scripts.prepare_models
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml run --rm tests
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml stop
```

浏览器恢复回归另需宿主机 Python 的 playwright 包与已安装的 Microsoft Edge；无需向应用容器安装浏览器：

```powershell
.\.venv\Scripts\python.exe tests/browser/check_registration.py
```

正向业务测试明确使用测试特征，验证事务和会话；真实模型无脸拒绝测试验证实际模型调用。真人成功样本验证仍需另行完成。测试结论见 [第二次作业验证记录](verification/week2-completion.md)。

## 6. 停止服务

```powershell
docker compose stop
```

此命令保留数据库、模型与照片卷，下次 `docker compose up -d --wait` 可恢复。不要执行删除卷的操作来解决普通启动问题。
