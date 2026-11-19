#!/usr/bin/env python3
"""AICB-9 local pilot CLI. Run from the PaperLeet-AICoding repository root."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from paperleet.tasks.aicb9.evaluators import evaluate_a01, evaluate_b01
from paperleet.tasks.aicb9.mutation import run_mutation_suite
from paperleet.tasks.aicb9.agent import AgentRunner, Budget, OpenAICompatibleClient
from paperleet.tasks.aicb9.registry import get_task


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aicb9")
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("task", choices=["A01", "B01"])
    evaluate.add_argument("--answer", required=True)
    mutate = commands.add_parser("mutate")
    mutate.add_argument("task", choices=["B03"])
    mutate.add_argument("--tests", required=True)
    agent = commands.add_parser("agent")
    agent.add_argument("task", choices=["C01"])
    agent.add_argument("--workspace", required=True)
    agent.add_argument("--instruction", type=Path, help="Override the bundled C01 workflow instructions")
    agent.add_argument("--max-tool-calls", type=int, default=24)
    agent.add_argument("--max-input-tokens", type=int, default=40000)
    agent.add_argument("--max-output-tokens", type=int, default=8000)
    agent.add_argument("--max-wall-seconds", type=float, default=120)
    args = parser.parse_args(argv)

    if args.command == "evaluate":
        report = evaluate_a01(args.answer) if args.task == "A01" else evaluate_b01(args.answer)
    elif args.command == "mutate":
        report = run_mutation_suite(args.tests)
    else:
        task_directory = get_task(args.task)["directory"]
        statement = (task_directory / "statement.md").read_text(encoding="utf-8")
        workflow = args.instruction or task_directory / "agent_instruction.md"
        instruction = f"{statement}\n\n{workflow.read_text(encoding='utf-8')}"
        client = OpenAICompatibleClient()
        budget = Budget(args.max_tool_calls, args.max_input_tokens, args.max_output_tokens, args.max_wall_seconds)
        report = AgentRunner(client, args.workspace, budget=budget).run(instruction)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if args.command in ("evaluate", "mutate") and not report.get("passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
