# B01 · Root Cause Diagnosis

## Issue

部分订单在购买多个相同商品时，折扣后金额与税费出现一两分钱的偏差。单件商品的测试大多通过，多件商品或特定小数价格时失败。

## 业务契约

- 金额使用 `Decimal`，不使用二进制浮点数。
- 折扣作用于整行金额：单价 × 数量 × (1 − 折扣率)。
- 每行折扣后小计按 `ROUND_HALF_UP` 舍入到分。
- 税费基于所有行小计之和计算，再按 `ROUND_HALF_UP` 舍入到分。

## 任务

阅读 `fixtures/ministore/b01/repository/src/ministore/pricing.py`，提交结构化诊断。不要修改代码。

填写 `starter_answer.json` 中的：

- `root_cause_id`：最主要根因标签。
- `primary_file`、`affected_function`：根因位置。
- `causal_order`：正确的计算顺序。
- `evidence_ids`：支持判断的证据标签。
- `excluded_hypotheses`：至少排除一个看似合理但不符合证据的假设。

示例计算：`19.95 × 3 × 0.9 = 53.865`，整行舍入后为 `53.87`。如果先把折后单价 `17.955` 舍入为 `17.96` 再乘以 3，则会得到 `53.88`。
