# 接口契约

## 实现状态

P1-01 仅实现 `GET /`、`GET /api/health/live`、静态资源和 `/api/docs`。
以下业务契约是 P3–P5 的实现目标，不注册返回假成功的占位接口。
OpenAPI 只展示已经实现的接口。服务入口遵循 [FastAPI 官方说明](https://fastapi.tiangolo.com/tutorial/first-steps/)。

## 通用规则

- 下表路径均带 `/api` 前缀。带照片的请求使用 multipart/form-data，文件字段固定为 `photo`；其余写请求使用 JSON。
- 数据库 id 为正整数；`session_code` 是随机公开场次码；`task_id` 为 UUID 字符串。三者不可互换。
- 字段使用 snake_case。日期使用带时区的 ISO 8601 字符串；服务端存 UTC，页面按 Asia/Shanghai 展示。
- 姓名 1–50 字、学号 1–32 个 ASCII 字母或数字、班级名 1–100 字、场次名 1–100 字；文本去首尾空格。密码 10–128 字符，不去空格、不静默截断。
- 写入字段采用白名单，未知字段拒绝。注册不能传 role，签到不能传 user_id/student_no。
- 列表使用 `page`（默认 1，最小 1）、`page_size`（默认 20，最大 100），响应 `{items, total, page, page_size}`，排序以 id 兜底保证稳定。
- 图片首版只支持 JPEG/PNG；字节、像素上限在 P2-02 通过共享配置落实，超限明确拒绝。
- 业务错误结构为 `{"error":{"code":"SESSION_ENDED","message":"本场次已结束","request_id":"..."}}`。错误消息不能包含密码、令牌、SQL 或内部文件路径；P1-04 接入统一处理与请求编号。
- 400 请求业务参数错误；401 未登录；403 权限或 CSRF 失败；404 资源不存在或不可见；409 幂等冲突/状态冲突；413 上传超限；415 格式不支持；422 字段不合法；429 限流；503 服务或队列不可用。

## 身份与权限

会话使用 HttpOnly Cookie，数据库仅存令牌哈希。登录返回 `csrf_token`，受保护写请求使用 `X-CSRF-Token`；刷新页面可通过 `/me` 取得当前会话 token。退出撤销服务端会话并清 Cookie。公开注册、登录、签到校验浏览器来源并限流，不要求已有登录会话。

普通用户只能操作本人资源；管理员可管理班级、场次及用户照片和记录。注册预留账户未完成人脸录入前不能登录。所有权限由服务端验证，前端隐藏按钮不构成授权检查。

## 账户与班级（P3）

| 方法与路径 | 权限 | 请求 | 成功结果 |
| --- | --- | --- | --- |
| GET /classes | 公开 | 分页 | 200，items 仅含有效班级 id/name |
| POST /classes | 管理员 | name | 201，id/name/status |
| POST /auth/register | 公开 | name/student_no/class_id/password/photo；Idempotency-Key 请求头 | 202，任务凭证；录入成功才激活 |
| POST /auth/register/{task_id}/retry | 原任务凭证 | photo；Idempotency-Key 与 X-Task-Token 请求头 | 202，新任务；仅可重试本人的失败注册 |
| POST /auth/login | 公开 | student_no/password | 200，user 与 csrf_token，并设置 Cookie |
| POST /auth/logout | 登录 | 无业务字段 | 204，撤销会话 |
| GET /me | 登录 | 无 | 200，user 与当前 csrf_token；禁止缓存 |
| GET /users | 管理员 | class_id（可选）、分页 | 200，人员列表，供照片库筛选 |

user 字段为 id/name/student_no/class_id/role/status，不返回 password_hash。登录失败统一反馈，不区分学号不存在或密码错误。

## 照片库（P3）

| 方法与路径 | 权限 | 请求 | 成功结果 |
| --- | --- | --- | --- |
| GET /faces | 登录 | user_id（仅管理员可指定）、分页 | 200，id/user_id/created_at/image_url |
| GET /faces/{id}/image | 登录且有资源权限 | 无 | 200，图片；私有、禁止共享缓存 |
| POST /faces | 登录且有资源权限 | photo、replace_id（可选）、user_id（仅管理员）；Idempotency-Key | 202，任务凭证 |
| DELETE /faces/{id} | 登录且有资源权限 | 无 | 204，使照片与特征失效 |

替换失败保留旧照片；删除最后一张后无法识别，但历史记录保留。image_url 指向受保护接口，不能是静态照片目录。响应不返回向量或文件系统路径。

## 课程场次（P4）

| 方法与路径 | 权限 | 请求 | 成功结果 |
| --- | --- | --- | --- |
| POST /sessions | 管理员 | title/class_id/starts_at/ends_at | 201，场次对象、expected_count、checkin_path |
| GET /sessions | 管理员 | class_id（可选）、分页 | 200，场次列表 |
| GET /sessions/{code} | 公开 | 公开场次码 | 200，title/class_name/starts_at/ends_at/effective_end/status/server_time |
| POST /sessions/{id}/close | 管理员 | 数字场次 id | 200，场次对象；重复关闭保留首次 closed_at |

管理场次对象含 id/public_code/title/class_id/starts_at/ends_at/closed_at/status。status 为 SCHEDULED/OPEN/CLOSED，由服务端计算。公开响应没有名单、人员信息。checkin_path 为 `/checkin.html?session_code=...`，前端结合当前来源生成链接。

创建时冻结有效学生名单，空名单拒绝；结束须晚于开始及创建时刻。发布后不编辑名单或时间。资格按完整接收并校验照片后的 received_at 判断，区间为 `[starts_at, effective_end)`。客户端时间只用于展示。

## 匿名签到与记录（P5）

| 方法与路径 | 权限 | 请求 | 成功结果 |
| --- | --- | --- | --- |
| POST /checkins | 公开 | session_code/photo；Idempotency-Key 请求头 | 202，任务凭证 |
| GET /records | 登录 | session_id（管理员必填，普通用户可选）、分页 | 200，个人记录或场次名单统计 |

签到先全库检索，再判断冻结名单。唯一约束 `(session_id,user_id)` 保证每人每场一次。未知人员不写任何人的成功记录。

个人记录 items 包含 id/session_id/session_title/received_at/recognized_at。管理员 items 从冻结名单返回 user_id/name/student_no/checkin_status/received_at；summary 包含 expected_count/checked_in_count/not_checked_in_count/pending_task_count/is_final。未签到使用 NOT_CHECKED_IN，已签到使用 CHECKED_IN。计数与分页无关，未结束或仍有有效任务时 is_final=false。本人接口不返回全班名单或统计。

## 异步任务（P3 起复用）

创建返回 HTTP 202，例如：

```json
{
  "task_id": "784a9ea2-a0ab-45ac-871c-5ab1f0f887cd",
  "task_token": "仅为示例，实际由服务器签发",
  "status": "PENDING",
  "poll_url": "/api/tasks/784a9ea2-a0ab-45ac-871c-5ab1f0f887cd"
}
```

`GET /tasks/{id}` 使用 `X-Task-Token` 请求头，或校验任务所有权的登录会话。凭证不放在 URL 中，不记录到日志。匿名签到没有可推断的登录所有者，必须持凭证查询；管理员也须经过授权检查。查询响应禁止缓存。

响应字段为 task_id/status/result_code/message/created_at/finished_at；结果只包含本次必要反馈，不展示候选列表、向量、完整学号或标准照。finished_at 在完成前为 null。

| 状态 | 含义 | 前端行为 |
| --- | --- | --- |
| PENDING | 已接收，等待执行 | 约 1 秒后轮询 |
| RUNNING | 处理中 | 继续轮询 |
| SUCCEEDED | 业务完成 | 停止，按结果码展示 |
| REJECTED | 业务拒绝 | 停止，显示重拍/无法签到原因 |
| FAILED | 系统失败或任务超时 | 停止，提示稍后重试 |

成功码：ENROLLED、FACE_SAVED、CHECKED_IN、ALREADY_CHECKED_IN。拒绝码：NO_FACE、MULTIPLE_FACES、LOW_QUALITY、UNKNOWN_PERSON、AMBIGUOUS_PERSON、NOT_IN_ROSTER、FACE_ALREADY_ENROLLED。失败码：MODEL_UNAVAILABLE、TASK_TIMEOUT、PROCESSING_FAILED。接收阶段的时间错误 SESSION_NOT_STARTED/SESSION_ENDED 直接以 409 返回，不创建可成功任务。

## 2026-10-07 自测修复补充

- 老师的场次列表提供“打开签到页面”和“复制签到链接”；HTTP 环境不能使用自动复制时，显示可选中的完整链接供手动复制。学生仍从自己的工作台发现场次，匿名签到仍不依赖登录或客户端身份。
- 上传终态结果显示后滚动到反馈；相册或相机选换照片后显示“照片已更换，请提交”，旧结果不继续对应新照片。
- 鉴权使用独立短事务并在返回前释放连接；照片写事务重新读取操作人员并校验有效状态和所有权。连接池大小仍为 5+5，未以扩大池大小解决并发相互等待。
- 前台 Redis 连接/读写超时为 1 秒且不自动重试；业务 MySQL 连接超时及连接池等待为 1 秒，读写超时为 2 秒。就绪检查使用独立小连接池与 1 秒读写超时。Celery 的后台重投递策略保持独立。
- Docker 服务退出后 DNS 可能等待数秒，单设 socket 超时不足以控制响应。前台依赖共用有界解析器：每个配置的主机名最多一个解析任务，最多两个解析线程，单次前台等待 250 ms，短暂复用上次地址并每秒更新，避免为每个请求创建新线程。地址重新可解析后刷新缓存；TLS 仍使用原主机名进行证书校验。
- 可识别的数据库连接异常及连接池等待超时返回 SERVICE_UNAVAILABLE/503；SQL 语法等程序错误仍为 INTERNAL_ERROR/500。错误正文与日志不包含 SQL、参数或凭据。
- 匿名签到来源 IP 的默认预算为每 60 秒 600 次，可由 CHECKIN_IP_RATE_LIMIT 调整；每场次在所有来源间共享 max(60, 冻结名单人数 × CHECKIN_ATTEMPTS_PER_STUDENT) 次预算，默认每人系数为 3。重复幂等键恢复已有任务时不消耗新的场次预算；新请求仍经过来源 IP 防护。系统总在途任务上限仍为 50，超限返回 QUEUE_FULL/503。
- 429 响应附带 Retry-After 剩余秒数；页面显示相应等待时间。照片库上传预算按已鉴权账号计算，避免不同学生共用网络出口时争抢同一预算。登录和注册的现有限流仍保留。
- 录入与替换在图库锁内检查其他有效账号的同模型人脸特征，达到既有匹配阈值时拒绝为 FACE_ALREADY_ENROLLED。注册账号保持 PENDING；替换失败保留原图。本人增加/替换本人其他照片可以正常完成，不返回其他账号身份信息。

Idempotency-Key 使用客户端生成的 UUID v4，同一次重试复用，重新拍照使用新键。服务端绑定操作、已登录所有者（如有）、场次和规范化请求内容；同键同内容返回原任务及可用凭证，同键不同内容返回 409。请求指纹不得保存明文密码；凭证重放实现见 P3-02。

接收过的签到请求重放先查幂等记录，再判断新请求时间，不能因轮询/重试过了截止时间而改写原 received_at。任务过期清理后返回明确的过期结果，不能把老键当作新的成功请求。HTTP 202 和正常轮询的 HTTP 200 均不代表签到成功。
