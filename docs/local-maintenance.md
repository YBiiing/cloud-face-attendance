# 本地维护、照片清理与备份恢复

## 1. 照片清理（默认只预览）

```powershell
docker compose run --rm --no-deps api python -m scripts.cleanup_storage
```

预览列出 eligible，但不删除文件。核对后显式执行：

```powershell
docker compose run --rm --no-deps api python -m scripts.cleanup_storage --apply --retention-hours 24
```

仅处理项目存储 uploads 目录下程序生成的 32 位十六进制 `.image` 文件；文件和引用任务完成时间都须超过保留期，最短 24 小时。有效标准照与任何非终态任务引用始终保留；路径跳出根目录、符号链接及非托管文件不删除。删除的终态任务图片路径设为空，任务状态和签到记录保留。已停用标准照可以清理，仍有效的标准照不能清理。

清理与人脸入库、替换采用相同的首个数据库锁，避免处理过程中误删将成为有效标准照的文件。删除失败会报错；不可恢复的磁盘硬件损坏不在该工具的恢复能力内。建议先备份再执行正式资料清理。本轮未对开发库运行 `--apply`。

## 2. 一致性备份

备份包含所有应用表的逻辑 MySQL 数据与其仍存在的照片，包括密码哈希等敏感字段；不包含模型权重和 APP_SECRET。它是应用级备份，不包含 MySQL 服务器账号、全局配置和其他数据库。

从仓库根目录执行，路径按自己的仓库位置修改：

```powershell
New-Item -ItemType Directory -Force private-backups
docker compose run --rm --no-deps -v E:/A-project/cloud-face-attendance/private-backups:/backup api python -m scripts.backup_data export --file /backup/local-backup.zip
```

同名文件已存在会拒绝覆盖。私有备份目录已加入 Git 忽略规则，不推送备份。APP_SECRET 与模型文件需要另外妥善保管；APP_SECRET 不同时，旧任务凭证不能保证继续使用。

备份期间在 MySQL 一致性快照中读取全部应用数据，并持有照片库状态锁直到关联文件读取完毕，使照片替换和清理不能跨越该快照。它会短暂阻塞照片入库/更新，建议在停止新操作后进行；并非零影响的在线大数据库备份方案。

## 3. 仅恢复到全新隔离测试环境

恢复程序限制 APP_ENV=test、MYSQL_DATABASE=face_attendance_test，验证数据库和照片存储为空、迁移版本一致、压缩包条目安全且校验和正确。**不提供覆盖开发库或生产库的恢复入口。**

下面项目名必须使用一个尚未使用的新名字，避免指向已有测试数据。示例 `face-attendance-restore-new`：

```powershell
docker compose -p face-attendance-restore-new -f compose.yaml -f compose.test.yaml up -d --wait mysql redis
docker compose -p face-attendance-restore-new -f compose.yaml -f compose.test.yaml run --rm migrate
docker compose -p face-attendance-restore-new -f compose.yaml -f compose.test.yaml run --rm --no-deps -v E:/A-project/cloud-face-attendance/private-backups:/backup:ro api python -m scripts.backup_data restore --file /backup/local-backup.zip --confirm-empty-test-database
docker compose -p face-attendance-restore-new -f compose.yaml -f compose.test.yaml run --rm --no-deps api python -m scripts.check_database
docker compose -p face-attendance-restore-new -f compose.yaml -f compose.test.yaml stop
```

使用 API 运行时镜像执行上述脚本，其环境由 compose.test.yaml 改为 test；无需启动 Web API 或 worker。不要在恢复期间启动该隔离环境的业务服务。恢复数据和照片后，模型仍需按运行手册准备，方能启动识别。

程序不使用 `extractall`，只写合法 UUID 照片路径；拒绝重复 ZIP 条目、目录穿越和大于 1 GiB 的解压总量。数据库非空或照片目录非空时直接拒绝。写入失败时数据库事务回滚，并清理本次已创建的文件；异常终止/断电后若留下文件，再次恢复会拒绝该非空目标，需新建隔离环境后重试。

## 4. 本地故障与压力验证

这些脚本固定操作 face-attendance-test，不接受公网或开发库地址；执行前先构建运行时镜像并按第二次说明准备隔离测试模型。

```powershell
docker compose build api
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml up -d --wait worker
.\.venv\Scripts\python.exe scripts/test_redis_recovery.py
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml -f compose.e2e.yaml up -d --wait api worker
.\.venv\Scripts\python.exe -m scripts.load_test
docker compose -p face-attendance-test -f compose.yaml -f compose.test.yaml -f compose.e2e.yaml --profile test-api stop
```

故障脚本会停止并恢复测试 Redis，不能与其他测试并行运行。压测每档分别提交 1、5、10、20 张空白图片，保留 IP 限速，记录 HTTP 拒绝、真实模型 NO_FACE、排队、处理和端到端耗时。它不是成功人脸签到吞吐量测试；真实人脸并发仍待真人样本。报告见 `docs/verification/local-load.json` 和 P6 验证记录。
