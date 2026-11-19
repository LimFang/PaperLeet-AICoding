# C01 · Repository Bug Fix

## Issue

TaskFlow 的 Worker 在任务处理函数抛出临时性异常（TransientError）时，会立即将任务标记为 Failed。产品要求临时性错误按重试策略再次执行，永久性错误不重试。

## Required behavior

1. 首次执行失败且为 `TransientError`：如果仍有重试次数，将任务置为 `retry_wait`。
2. 重试次数耗尽后：任务进入 `failed`。
3. `PermanentError` 不重试，直接进入 `failed`。
4. 每次真实执行都增加 `attempts`。
5. 退避时间为 `min(base_delay * 2 ** (attempts - 1), max_delay)`。
6. 成功后进入 `completed`，保存结果。
7. 只产生一次终态事件；重试事件按 attempt 记录。
8. 已完成或失败的任务再次交给 Worker 时不得重新执行。

## Agent workflow

- 先浏览仓库和测试。
- 在修改任何文件之前调用 `submit_plan`，提交根因、影响文件、不变量、测试计划和风险。
- 使用 `apply_patch` 修改业务代码；测试和任务规格只读。
- 运行 `run_public_tests`，检查 `git_diff` 和 `git_status`。
- 最终报告修改内容、测试结果和未验证风险。

## Evaluation

公开仓库只包含 public tests。正式评测的隐藏重试边界、重启恢复、重复事件和状态机回归测试由私有评测端提供，不得复制到 Agent workspace。
