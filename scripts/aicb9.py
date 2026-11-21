#!/usr/bin/env python3
"""AICB-9 local pilot CLI. Run from the PaperLeet-AICoding repository root."""
import argparse
from importlib import import_module
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from paperleet.providers import ModelConfig, OpenAICompatibleClient
from paperleet.tasks.aicb9.agent import AgentRunner, Budget
from paperleet.tasks.aicb9.registry import load_registry


def _registered_handler(task):
    """Resolve the trusted in-repository handler declared by this task's spec."""
    reference = task["cli"]["handler"]
    module_name, function_name = reference.split(":", 1)
    module = import_module(module_name)
    handler = getattr(module, function_name)
    if not callable(handler):
        raise ValueError(f"Task handler is not callable: {reference}")
    return handler


def _task_limits(task, args):
    """Use the task's declared execution limits unless explicitly overridden."""
    settings = task.get("execution", {})
    defaults = {
        "max_tool_calls": 24,
        "max_input_tokens": 40000,
        "max_output_tokens": 8000,
        "max_wall_seconds": 120,
    }
    return {name: getattr(args, name) if getattr(args, name) is not None
            else settings.get(name, default)
            for name, default in defaults.items()}


def _validate_clean_git_workspace(workspace):
    root = Path(workspace).resolve()
    check = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=root, capture_output=True, text=True,
    )
    if check.returncode != 0:
        raise ValueError("--workspace must be an existing Git repository")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root, capture_output=True, text=True,
    )
    if status.returncode != 0:
        raise ValueError("could not inspect workspace Git status")
    if status.stdout.strip():
        raise ValueError("--workspace must have a clean working tree before the run")
    return root


def main(argv=None, *, client_factory=None, config_factory=None):
    registry = load_registry()
    tasks_by_mode = {
        command: [task for task in registry if task.get("cli", {}).get("command") == command]
        for command in ("evaluate", "mutate", "agent")
    }

    parser = argparse.ArgumentParser(prog="aicb9")
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("task", choices=[task["id"] for task in tasks_by_mode["evaluate"]])
    evaluate.add_argument("--answer", required=True)
    mutate = commands.add_parser("mutate")
    mutate.add_argument("task", choices=[task["id"] for task in tasks_by_mode["mutate"]])
    mutate.add_argument("--tests", required=True)
    agent = commands.add_parser("agent")
    agent.add_argument("task", choices=[task["id"] for task in tasks_by_mode["agent"]])
    agent.add_argument("--workspace", required=True)
    agent.add_argument("--instruction", type=Path, help="Override the bundled agent workflow instructions")
    agent.add_argument("--max-tool-calls", type=int)
    agent.add_argument("--max-input-tokens", type=int)
    agent.add_argument("--max-output-tokens", type=int)
    agent.add_argument("--max-wall-seconds", type=float)
    smoke = commands.add_parser("smoke", help="make one explicitly confirmed real model API request")
    smoke.add_argument("--model", required=True, help="exact model ID enabled for your API account")
    smoke.add_argument(
        "--confirm-paid-api",
        action="store_true",
        required=True,
        help="confirm that this command sends one real API request and may incur charges",
    )
    args = parser.parse_args(argv)

    if args.command == "smoke":
        try:
            factory = config_factory or ModelConfig.from_env
            config = factory(model=args.model)
        except ValueError as exc:
            parser.error(str(exc))
        client = (client_factory or OpenAICompatibleClient)(config=config)
        messages = [
            {
                "role": "system",
                "content": "This is an API connectivity smoke test. Reply with exactly PAPERLEET_SMOKE_OK.",
            },
            {"role": "user", "content": "Reply with exactly PAPERLEET_SMOKE_OK."},
        ]
        started = time.monotonic()
        try:
            response = client.complete(messages, [], 32)
            choice = response.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content") if isinstance(message, dict) else None
            usage = response.get("usage", {})
            usage = usage if isinstance(usage, dict) else {}
            input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
            output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
            matched = isinstance(content, str) and content.strip() == "PAPERLEET_SMOKE_OK"
            report = {
                "status": "succeeded" if matched else "unexpected_response",
                "provider": config.provider,
                "model": config.model,
                "api_calls": 1,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "usage_source": (
                    "provider_reported"
                    if input_tokens is not None or output_tokens is not None else "unavailable"
                ),
                "wall_time_seconds": round(time.monotonic() - started, 6),
                "cost_usd": None,
                "price_table_version": None,
                "response": content,
            }
        except Exception as exc:
            report = {
                "status": "failed",
                "provider": config.provider,
                "model": config.model,
                "api_calls": 1,
                "wall_time_seconds": round(time.monotonic() - started, 6),
                "error_type": type(exc).__name__,
                "cost_usd": None,
                "price_table_version": None,
            }
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0 if report["status"] == "succeeded" else 1

    task = next(task for task in tasks_by_mode[args.command] if task["id"] == args.task)
    if args.command == "evaluate":
        report = _registered_handler(task)(args.answer)
    elif args.command == "mutate":
        report = _registered_handler(task)(args.tests)
    else:
        task_directory = task["directory"]
        statement = (task_directory / "statement.md").read_text(encoding="utf-8")
        workflow = args.instruction or task_directory / "agent_instruction.md"
        instruction = f"{statement}\n\n{workflow.read_text(encoding='utf-8')}"
        client = (client_factory or OpenAICompatibleClient)()
        try:
            workspace = _validate_clean_git_workspace(args.workspace)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        limits = _task_limits(task, args)
        budget = Budget(limits["max_tool_calls"], limits["max_input_tokens"],
                        limits["max_output_tokens"], limits["max_wall_seconds"])
        report = AgentRunner(client, workspace, budget=budget).run(instruction)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if args.command in ("evaluate", "mutate") and not report.get("passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
