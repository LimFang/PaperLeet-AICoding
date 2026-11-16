import { ArrowRight, Code2, FlaskConical, GitBranch, Terminal } from "lucide-react";
import { useI18n } from "./i18n";
import { collectionHref } from "./navigation";

const tracks = [
  {
    number: "01", icon: Code2, name: "Coding Agent 工程", nameEn: "Coding Agent engineering",
    role: "AI Coding · 研发工具", roleEn: "AI Coding · Developer tools",
    description: "接入模型 API，让 Agent 理解仓库、调用工具、修改代码并验证结果。",
    descriptionEn: "Connect a model API and build an agent that explores repositories, uses tools, edits code and verifies results.",
    lessons: ["模型 API 与工具执行器", "仓库检索与上下文选择", "Bug 修复与跨文件修改", "测试反馈循环与任务预算"],
    lessonsEn: ["Model APIs and tool execution", "Repository retrieval and context selection", "Bug fixes and cross-file edits", "Test feedback loops and task budgets"],
    outcome: "交付：补丁、执行轨迹、修复成功率", outcomeEn: "Deliver: patches, execution traces and fix success rates",
    foundation: "llm-basics", foundationName: "LLM 基础", foundationNameEn: "LLM foundations",
  },
  {
    number: "02", icon: Terminal, name: "质量智能与研发效能", nameEn: "Quality & developer productivity",
    role: "LLM for SE · AIOps", roleEn: "LLM for SE · AIOps",
    description: "把 RAG 和 Agent 放进真实研发流程，练习测试生成、证据检索与故障定位。",
    descriptionEn: "Apply RAG and agents to development workflows: test generation, evidence retrieval and incident diagnosis.",
    lessons: ["代码库问答与证据引用", "基于代码变更生成测试", "日志 / Trace 根因分析", "任务集评测与失败归因"],
    lessonsEn: ["Codebase Q&A with evidence", "Test generation from code changes", "Root cause analysis with logs and traces", "Task evaluation and failure analysis"],
    outcome: "交付：测试用例、根因证据、评测报告", outcomeEn: "Deliver: tests, root cause evidence and evaluation reports",
    foundation: "retrieval", foundationName: "检索算法基础", foundationNameEn: "Retrieval foundations",
  },
  {
    number: "03", icon: FlaskConical, name: "Agent 数据与后训练", nameEn: "Agent data & post-training",
    role: "Agentic RL · 算法研究", roleEn: "Agentic RL · Algorithm research",
    description: "从执行轨迹构建训练数据，研究 SFT、奖励设计与 RL 对长链路任务的影响。",
    descriptionEn: "Build training data from execution traces and study SFT, reward design and RL for long-running tasks.",
    lessons: ["轨迹清洗与训练集构建", "Agent SFT 与独立任务评测", "结果奖励与过程奖励", "RL 优化与消融实验"],
    lessonsEn: ["Trace curation and dataset construction", "Agent SFT and held-out evaluation", "Outcome and process rewards", "RL optimization and ablation studies"],
    outcome: "交付：数据集、训练配置、效果对比", outcomeEn: "Deliver: datasets, training configs and comparative results",
    foundation: "post-training", foundationName: "后训练算法基础", foundationNameEn: "Post-training foundations",
  },
];

export default function AgentHome() {
  const { t } = useI18n();
  function showFoundations() {
    document.getElementById("algorithm-foundations")?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  }
  return <>
    <section className="agent-hero" aria-labelledby="agent-home-title">
      <div className="agent-hero-copy">
        <p className="agent-eyebrow"><span /> AI CODING · LLM FOR SOFTWARE ENGINEERING</p>
        <h1 id="agent-home-title">{t("构建能完成研发任务的", "Build a reliable")}<br /><span>Coding Agent</span></h1>
        <p className="agent-hero-description">{t("从模型 API、代码检索与工具调用，到自动修复、智能排障和 Agent 后训练。围绕研发任务练习，用测试、执行轨迹与实验结果验证改进。", "From model APIs, code retrieval and tool use to bug fixing, incident diagnosis and agent post-training. Practice development tasks and validate improvements with tests, execution traces and experiments.")}</p>
        <div className="agent-hero-actions">
          <button className="button" onClick={() => document.getElementById("agent-paths")?.scrollIntoView()}>{t("查看岗位能力路径", "Explore career paths")}<ArrowRight size={16} /></button>
          <button className="button subtle" onClick={showFoundations}>{t("开始算法基础练习", "Practice algorithm foundations")}</button>
        </div>
        <p className="agent-availability">{t("当前可练：论文算法基础 · Agent 场景练习规划中", "Available now: algorithm foundations · Agent exercises are planned")}</p>
      </div>
      <div className="agent-workflow" aria-label={t("目标任务流程示意", "Target task workflow")}>
        <div className="agent-workflow-heading"><GitBranch size={16} /><span>{t("目标任务 / 自动修复 Bug", "TARGET TASK / BUG REPAIR")}</span><span className="agent-outline-label">{t("流程示意", "WORKFLOW")}</span></div>
        {[
          ["01", "理解任务", "Understand", "Issue + 仓库上下文", "Issue + repository context"],
          ["02", "检索与行动", "Retrieve & act", "搜索代码 → 调用工具 → 生成补丁", "Search code → use tools → create a patch"],
          ["03", "执行与反馈", "Execute & iterate", "运行测试 → 分析失败 → 修正实现", "Run tests → analyze failures → revise"],
          ["04", "评测与优化", "Evaluate & improve", "成功率 · 调用成本 · 回归结果", "Success rate · API cost · Regressions"],
        ].map(([number, name, nameEn, detail, detailEn]) => <div className="agent-workflow-step" key={number}><span>{number}</span><div><strong>{t(name, nameEn)}</strong><p>{t(detail, detailEn)}</p></div></div>)}
        <div className="agent-workflow-footer"><Terminal size={14} />{t("交付代码，也交付可复核的执行证据", "Ship code with verifiable execution evidence")}</div>
      </div>
    </section>
    <section className="agent-paths" id="agent-paths" aria-labelledby="agent-paths-title">
      <div className="agent-section-heading"><div><p className="agent-eyebrow">ROLE-ORIENTED LEARNING</p><h2 id="agent-paths-title">{t("围绕目标岗位，选择练习方向", "Choose a path for your target role")}</h2></div><span className="agent-outline-label">{t("场景课程规划", "PLANNED CURRICULUM")}</span></div>
      <p className="agent-section-note">{t("展开查看各方向的任务与交付物；卡片底部可进入现有算法基础题。", "Expand each path to see tasks and deliverables. Foundation links open existing algorithm exercises.")}</p>
      <div className="agent-track-grid">{tracks.map((track) => <details className="agent-track" key={track.number}>
        <summary><div className="agent-track-meta"><track.icon size={21} /><span>{track.number} / {track.roleEn}</span></div><h3>{t(track.name, track.nameEn)}</h3><p>{t(track.description, track.descriptionEn)}</p><span className="agent-track-toggle">{t("查看练习规划", "View planned exercises")}<ArrowRight size={15} /></span></summary>
        <div className="agent-track-body"><ol>{track.lessons.map((lesson, index) => <li key={lesson}>{t(lesson, track.lessonsEn[index])}</li>)}</ol><p>{t(track.outcome, track.outcomeEn)}</p><a href={collectionHref(track.foundation)}>{t(track.foundationName, track.foundationNameEn)}<ArrowRight size={14} /></a></div>
      </details>)}</div>
    </section>
  </>;
}
