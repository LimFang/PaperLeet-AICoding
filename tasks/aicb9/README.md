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

## 版本化任务元数据

`registry.yaml` 使用 `schema_version: 2`，四道题的 `task.yaml` 新增以下字段，同时保留原有的 `scoring`、`runtime`、`execution`、`api_required` 和 `repository`，避免改变现有评分和执行语义。

| 字段 | 含义 |
|---|---|
| `task_version` | 题目及输入契约的语义版本 |
| `rubric_version` | 评分细则版本；修改评分规则时必须更新 |
| `cli.command` / `cli.handler` | 现有 CLI 运行模式和本地可信判题入口 |
| `interfaces` | 题面/输出契约文件路径与答案格式（相对于 `tasks/aicb9/`） |
| `strategies.supported` | 已有统一策略适配器、真实可运行的 S0–S3 策略 |
| `strategies.planned` | 规划中的策略；不能当作已实现 |
| `fixture.version` / `fixture.digest` | 题目仓库版本和文件树 Git SHA-1 摘要 |
| `evaluation.public` / `evaluation.private` | 公开与可信私有评分组件的实现状态 |

当前四道题的 `strategies.supported` 都为空，表示统一 S0–S3 执行适配器仍未实现；C01 已有的本地 Agent 原型继续通过 `agent C01` 命令运行，不应误写成标准化 S3 适配器已完成。B03 的六个变异体属于公开开发样例，C01 隐藏评分状态为 `not_implemented`。

注册表加载时会检查任务 ID/Slug/编号、版本、输入输出文件、策略名称、分数权重和预算类型。为了兼容旧扩展，缺少 `schema_version` 的旧版注册表仍可读取，但新任务应遵循 v2。所有本地 CLI 的任务列表由注册表的 `cli.command` 字段生成，不再单独硬编码题号。

## 统一 Benchmark Runner（实验接口）

安装项目后，可以使用统一入口执行已声明支持的任务/策略组合。已有答案的确定性评分不需要模型 API：

```bash
paperleet-benchmark evaluate --task A01 --answer tasks/aicb9/A01/reference_trace.json
paperleet-benchmark evaluate --task B01 --answer /path/to/diagnosis.json
```

模型策略运行需要配置 API：

```bash
# 配置模型 API；--model 指定精确模型 ID。
export AICB9_API_KEY="..."
export AICB9_BASE_URL="https://api.deepseek.com"
export AICB9_PROVIDER="openai_compatible"

# A01：Black-box Single-Prompt
paperleet-benchmark run --task A01 --model "<model-id>" --strategy s0 --seed 42

# A01：White-box Single-Prompt（只额外提供方法步骤）
paperleet-benchmark run --task A01 --model "<model-id>" --strategy s1 \
  --method-steps-file /path/to/method-steps.md

# B01：Tool-Augmented Single-Prompt（证据由调用方预先生成）
paperleet-benchmark run --task B01 --model "<model-id>" --strategy s2 \
  --evidence-file /path/to/evidence.txt

# C01：Agentic；默认复制公开 fixture 到临时 Git 工作区
paperleet-benchmark run --task C01 --model "<model-id>" --strategy s3 \
  --output reports/benchmark/c01-run.json
```

Runner 会记录任务/Fixture 版本、策略、模型、Prompt Hash、运行时间、调用数、Token 使用情况和产物摘要。当前 OpenAI-compatible adapter 不向模型请求传递随机种子，因此 `seed` 只记录为实验元数据，报告会明确标记 `seed_applied: false`。未获得 Provider usage 时，Token 字段保持 `null`；成本在引入版本化价格表前保持 `null`。

当前可运行组合以各题 `task.yaml` 的 `strategies.supported` 为准：A01/B01 支持 S0/S1/S2，C01 支持 S3；B03 暂不支持统一 Runner。C01 的可信隐藏测试评分仍未实现，报告不会伪造隐藏测试分数。S3 本地执行仅适用于可信代码，不是公网不可信代码沙箱。

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
