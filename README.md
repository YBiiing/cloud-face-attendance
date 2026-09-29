# cloud-face-attendance

云计算课程人脸签到系统，采用手机 H5、FastAPI、MySQL 和服务器端人脸识别。

## 设计文档

- [第一次提交简要设计文档 Markdown 版](docs/design.md)
- [第一次提交简要设计文档 Word 版](docs/人脸签到系统简要设计文档.docx)
- [本地开发详细计划](docs/local-development-plan.md)：六个阶段、28 个任务，包含依赖、交付物与验收条件。

## 第二次作业

注册、登录、退出登录、拍照选择与上传的本地编码已完成，提供 [启动与提交说明](docs/week2-submission.md) 和 [验证记录](docs/verification/week2-completion.md)。真人成功录入、实际手机操作及相应截图仍需补齐；当前不声明整份作业已经验收。

## 第三次作业

匿名限时签到、全库身份检索、名单校验、重复签到保护、个人记录与管理员统计已实现。操作见 [第三次演示说明](docs/week3-submission.md)，验收边界见 [本地功能验收记录](docs/verification/local-functional.md)。按用户要求先完成编码和自动化验证，真人与手机实测后补。

## 开发进度

P1 基础环境和 P4 场次管理已完成；P2 模型、P3 注册登录与照片库已实现，真人照片成功录入和效果验收待补。P5 匿名签到与记录编码完成，真人实测待补。每小任务验证后 commit，每阶段验收后 push；云部署最后进行。

- [运行手册](docs/local-runbook.md)
- [接口契约](docs/api-contract.md)
- [P1-01 验证记录](docs/verification/p1-01.md)
- [P1 阶段验收](docs/verification/p1-04.md)
