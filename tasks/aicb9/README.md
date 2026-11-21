# AICB-9 · Phase 1

首批样板题：A01、B01、B03、C01。AICB-9 将人类工程推理练习与 Coding Agent 任务分开评测，但复用任务仓库、工具契约和确定性执行基础。

## Benchmark 协议与实现状态

AICB-9 的对照协议定义了 S0 Black-box Single-Prompt、S1 White-box Single-Prompt、S2 Tool-Augmented Single-Prompt 和 S3 Agentic。协议定义不代表统一 Runner 或四种策略适配器已经全部实现；当前任务仍按下文所述的本地 CLI 路径运行。协议和指标见 [Benchmark Protocol](../../docs/benchmark-protocol.md)、[Evaluation Metrics](../../docs/evaluation-metrics.md)、[Reproducibility](../../docs/reproducibility.md) 和 [Scoring Rules](../../docs/scoring-rules.md)。

当前状态需要特别区分：A01/B01 使用确定性结构化评分；B03 仓库中可见的六个 Mutants 是本地开发/演示样例，不是正式隐藏评测资产；C01 的本地 Agent 原型尚未接入可信隐藏测试评分，因此本地报告不能声称获得了隐藏测试分数。

| ID | 题目 | 形式 | 模型 API |
|---|---|---|---|
| A01 | [Trace the Execution](A01/statement.md) | 结构化执行轨迹 | 不需要 |
| B01 | [Root Cause Diagnosis](B01/statement.md) | 结构化根因诊断 | 不需要 |
| B03 | [Test the Hidden Bug](B03/statement.md) | 学生编写测试 + Mutation Testing | 不需要 |
| C01 | [Repository Bug Fix](C01/statement.md) | 仓库级 Agent 修复 | 真实运行需配置 DeepSeek 或兼容 API |

## 本地运行

安装项目的 Python 依赖后，在仓库根目录运行以下命令。做 A01 或 B01 时，先复制题目目录中的 `starter_answer.json`，填完后将其路径传给 `--answer`。做 B03 时，将自己的 pytest 文件传给 `--tests`。

```bash
python scripts/aicb9.py evaluate A01 --answer tasks/aicb9/A01/reference_trace.json
python scripts/aicb9.py evaluate B01 --answer /path/to/diagnosis.json
python scripts/aicb9.py mutate B03 --tests tests/aicb9/submissions/b03_reference_contract.py
python -m pytest tests/aicb9 -q
```

运行 C01 前，在环境中设置 `DEEPSEEK_API_KEY` 和账号可用的 `AICB9_MODEL`。兼容其他提供方时，使用 `AICB9_API_KEY` 和 `AICB9_BASE_URL`。每次运行从一份干净的题目仓库开始。

```bash
task_workspace="$(mktemp -d)"
cp -R tasks/aicb9/fixtures/taskflow/repository/. "$task_workspace/"
git -C "$task_workspace" init --quiet
git -C "$task_workspace" add .
git -C "$task_workspace" -c user.name=PaperLeet -c user.email=paperleet@example.invalid \
    commit --quiet -m "Initialize C01 fixture"
python scripts/aicb9.py agent C01 --workspace "$task_workspace"
```

命令会将 C01 题面和操作说明发给模型，并在标准输出返回计划、工具调用轨迹和预算使用量。当前验收使用模拟模型与公开测试。

## 开发约束

- 任务目录独立于 `problems/`，不进入论文算法题库同步流程。
- A01/B01 使用确定性 rubric，不调用 LLM-as-a-judge。
- B03 的六个 Mutants 用于本地开发验收；公开发布时，真正的 benchmark 变异体与测试必须放在私有评测服务。
- C01 只公开仓库、Issue 和 public tests。隐藏测试必须由可信评测端注入，不能放进 Agent workspace。
- B03 与 C01 会以当前用户的权限执行本地 Python，只用于可信代码。托管评测需要独立的操作系统级隔离。

## Phase 1 acceptance

1. `python -m pytest tests/aicb9 -q` 通过。
2. A01、B01 的示例答案得到确定性分数。
3. B03 示例测试通过 reference 并杀死六个 Mutants。
4. C01 的工具预算、计划门控和路径保护通过 mock 测试。
5. C01 不进行真实 API 调用；真实 API 联调需用户自行配置密钥和模型 ID。
