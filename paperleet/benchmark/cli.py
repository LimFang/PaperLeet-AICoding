"""Command-line entry point for generic AICB-9 benchmark runs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from paperleet.providers import ModelConfig, OpenAICompatibleClient
from paperleet.tasks.aicb9.agent import AgentRunner, Budget
from paperleet.tasks.aicb9.registry import load_registry
from .runner import BenchmarkRunner
from .strategies import (
    AgenticStrategy,
    BlackBoxSinglePrompt,
    EvidenceBundle,
    StrategyRequest,
    ToolAugmentedSinglePrompt,
    WhiteBoxSinglePrompt,
)


_EXCLUDED_PARTS = {".git", ".env", ".venv", "venv", "node_modules", "__pycache__",
                   "tests", "test", "reference", "hidden", "private", "mutants", "secrets"}


def _repository_context(root: Path, max_characters: int = 24000) -> str:
    chunks = []
    used = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in _EXCLUDED_PARTS for part in relative.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not content.strip():
            continue
        chunk = f"\n--- FILE: {relative.as_posix()} ---\n{content}\n"
        if used + len(chunk) > max_characters:
            chunks.append("\n[Repository context truncated at the configured character limit.]")
            break
        chunks.append(chunk)
        used += len(chunk)
    return "".join(chunks) if chunks else "[No readable source files found in the task fixture.]"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _ensure_git_workspace(workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    inside = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=workspace, capture_output=True, text=True,
    )
    if inside.returncode == 0:
        return
    _git(workspace, "init", "--quiet")
    _git(workspace, "add", ".")
    _git(workspace, "-c", "user.name=PaperLeet", "-c",
         "user.email=paperleet@example.invalid", "commit", "--quiet", "-m", "Initialize benchmark fixture")


def _build_single_prompt_request(task: dict, strategy_id: str, args) -> StrategyRequest:
    task_directory = task["directory"]
    base = task_directory.parent
    statement = (task_directory / "statement.md").read_text(encoding="utf-8")
    repository = (base / task["repository"]).resolve()
    context = _repository_context(repository)
    output_contract_path = (base / task["interfaces"]["output"]).resolve()
    output_contract = output_contract_path.read_text(encoding="utf-8")
    user_content = (
        f"Benchmark task: {task['id']} — {task['title']}\n\n"
        f"{statement}\n\n"
        f"Repository snapshot:\n{context}\n\n"
        f"Required output format ({task['interfaces']['format']}):\n"
        f"{output_contract}\n\n"
        "Return only the requested output. Do not claim that tests were executed."
    )
    messages = [
        {"role": "system", "content": "You are completing a software-engineering benchmark. Follow the task statement and output contract exactly."},
        {"role": "user", "content": user_content},
    ]
    method_steps = None
    evidence = None
    if strategy_id == "S1":
        if not args.method_steps_file:
            raise ValueError("S1 requires --method-steps-file")
        method_steps = Path(args.method_steps_file).read_text(encoding="utf-8")
    if strategy_id == "S2":
        if not args.evidence_file:
            raise ValueError("S2 requires --evidence-file")
        evidence_path = Path(args.evidence_file)
        evidence_content = evidence_path.read_text(encoding="utf-8")
        evidence = EvidenceBundle(
            content=evidence_content,
            provenance=({
                "source": evidence_path.name,
                "version": "user_supplied",
                "digest": "sha256:" + hashlib.sha256(evidence_content.encode("utf-8")).hexdigest(),
            },),
        )
    return StrategyRequest(
        messages=messages,
        max_output_tokens=args.max_output_tokens or 2048,
        method_steps=method_steps,
        evidence=evidence,
    )


def _build_agentic_request(task: dict, args, workspace: Path, client_factory) -> tuple[StrategyRequest, AgenticStrategy]:
    task_directory = task["directory"]
    instruction = (
        (task_directory / "statement.md").read_text(encoding="utf-8")
        + "\n\n"
        + (task_directory / "agent_instruction.md").read_text(encoding="utf-8")
    )
    limits = task.get("budget_limits", {})
    budget = Budget(
        max_tool_calls=args.max_tool_calls or limits.get("max_tool_calls", 24),
        max_input_tokens=args.max_input_tokens or limits.get("max_input_tokens", 40000),
        max_output_tokens=args.max_output_tokens or limits.get("max_output_tokens", 8000),
        max_wall_seconds=args.max_wall_seconds or limits.get("max_wall_seconds", 120),
    )
    strategy = AgenticStrategy(AgentRunner(client_factory, workspace, budget=budget))
    return StrategyRequest(instruction=instruction, max_output_tokens=budget.max_output_tokens), strategy


def main(argv=None, *, client_factory=OpenAICompatibleClient, registry_loader=load_registry):
    tasks = registry_loader()
    parser = argparse.ArgumentParser(prog="paperleet-benchmark")
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser("evaluate", help="score an existing structured answer locally; no model API required")
    evaluate.add_argument("--task", required=True, choices=("A01", "B01"))
    evaluate.add_argument("--answer", required=True, type=Path)
    evaluate.add_argument("--output", type=Path, help="write the JSON report to this path instead of stdout")

    run = commands.add_parser("run", help="run one registered benchmark task with a model strategy")
    run.add_argument("--task", required=True, choices=[task["id"] for task in tasks])
    run.add_argument("--model", required=True, help="exact model ID; provider/base URL come from AICB9 environment settings")
    run.add_argument("--strategy", required=True, choices=("s0", "s1", "s2", "s3"))
    run.add_argument("--seed", type=int)
    run.add_argument("--output", type=Path, help="write the JSON report to this path instead of stdout")
    run.add_argument("--method-steps-file", type=Path)
    run.add_argument("--evidence-file", type=Path)
    run.add_argument("--workspace", type=Path, help="existing C01 workspace for S3; otherwise a temporary fixture copy is used")
    run.add_argument("--max-output-tokens", type=int)
    run.add_argument("--max-tool-calls", type=int)
    run.add_argument("--max-input-tokens", type=int)
    run.add_argument("--max-wall-seconds", type=float)
    args = parser.parse_args(argv)

    if args.command == "evaluate":
        report = BenchmarkRunner({}, tasks=tasks).evaluate(args.task, args.answer)
        rendered = json.dumps(report, ensure_ascii=False, indent=2, default=str)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\\n", encoding="utf-8")
        else:
            print(rendered)
        return 0 if report["status"] == "succeeded" else 1

    task = next(task for task in tasks if task["id"] == args.task)
    strategy_id = args.strategy.upper()
    if strategy_id not in (task.get("strategies") or {}).get("supported", []):
        parser.error(
            f"{strategy_id} is not supported for {task['id']}; "
            f"supported: {', '.join(task.get('strategies', {}).get('supported', [])) or 'none'}"
        )

    try:
        config = ModelConfig.from_env(model=args.model)
    except ValueError as exc:
        parser.error(str(exc))
    client = client_factory(config=config)
    model_metadata = config.public_metadata()
    strategies = {}
    temporary = None
    try:
        if strategy_id == "S3":
            if args.workspace:
                workspace = args.workspace.resolve()
                check = subprocess.run(
                    ["git", "rev-parse", "--is-inside-work-tree"],
                    cwd=workspace, capture_output=True, text=True,
                )
                if check.returncode != 0:
                    raise ValueError("--workspace must point to an existing Git repository")
            else:
                temporary = tempfile.TemporaryDirectory(prefix=f"paperleet-{task['id'].lower()}-")
                workspace = Path(temporary.name) / "repository"
                source = (task["directory"].parent / task["repository"]).resolve()
                shutil.copytree(source, workspace)
                _ensure_git_workspace(workspace)
            request, strategy = _build_agentic_request(task, args, workspace, client)
            strategies[strategy_id] = strategy
        else:
            request = _build_single_prompt_request(task, strategy_id, args)
            if strategy_id == "S0":
                strategies[strategy_id] = BlackBoxSinglePrompt(client)
            elif strategy_id == "S1":
                strategies[strategy_id] = WhiteBoxSinglePrompt(client)
            else:
                strategies[strategy_id] = ToolAugmentedSinglePrompt(client)

        report = BenchmarkRunner(strategies, tasks=tasks).run(
            task["id"], strategy_id, request,
            model_metadata=model_metadata,
            seed=args.seed,
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(f"benchmark setup failed: {type(exc).__name__}")
    finally:
        if temporary is not None:
            temporary.cleanup()

    rendered = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if report["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
