# P2-05 真实样本试验（待照片）

评估脚本已提供，但尚无经本人同意的人脸样本，不能报告准确率或校准阈值。P2 阶段暂不做“全部完成”的推送；可继续独立的业务开发。

在 Git 忽略目录 private-samples 中准备 manifest.json：

```json
{
  "gallery": [{"user_id": 1, "file": "person1-standard.jpg"}],
  "probes": [
    {"user_id": 1, "file": "person1-new.jpg"},
    {"user_id": null, "file": "unknown-person.jpg"}
  ]
}
```

建议至少两名已知人员和一名未知人员；分别建立调参集与验收集，不能复用同一照片。通过只读挂载 private-samples 和模型卷运行 `python -m scripts.evaluate_faces /samples/manifest.json --threshold 0.5 --margin 0.05`。示例阈值不是已验证参数。

脚本只输出模型版本、人数/照片数、阈值、总耗时及分类计数，不输出照片、人名或原始向量。实际试验后补充机器配置、独立验收集结果，并记录误识别情况。
