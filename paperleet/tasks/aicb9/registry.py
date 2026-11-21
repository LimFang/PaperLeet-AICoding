"""Filesystem registry for AICB-9 tasks; independent of the algorithm catalog.

Registry schema v2 adds versioned metadata and validates task contracts.
Legacy schema v1 task files remain readable for downstream consumers.
"""
from pathlib import Path, PurePosixPath
import os
import re
import yaml


_TASK_ID = re.compile(r"[A-Z][0-9]{2}")
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?")
_DIGEST = re.compile(r"(?:git-tree-sha1:[0-9a-f]{40}|sha256:[0-9a-f]{64})")
_HANDLER = re.compile(r"paperleet\.tasks\.aicb9\.[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*")
_STRATEGIES = {"S0", "S1", "S2", "S3"}
_CLI_COMMANDS = {"evaluate", "mutate", "agent"}
_STATUSES = {"implemented", "pilot", "not_implemented", "not_applicable"}
_OUTPUT_FORMATS = {"json", "pytest_file", "repository_patch"}
_INTEGER_LIMITS = {"max_tool_calls", "max_input_tokens", "max_output_tokens", "max_api_calls"}
_NUMBER_LIMITS = {"max_wall_seconds", "timeout_seconds", "max_cost_usd"}


def repo_root() -> Path:
    return Path(os.environ.get("PAPERLEET_ROOT", Path(__file__).resolve().parents[3])).resolve()


def task_root() -> Path:
    return Path(os.environ.get("AICB9_TASK_ROOT", repo_root() / "tasks" / "aicb9")).resolve()


def _mapping(value, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def _semver(value, label: str) -> str:
    if not isinstance(value, str) or not _SEMVER.fullmatch(value):
        raise ValueError(f"{label} must be a semantic version (e.g. 1.0.0)")
    return value


def _reference(base: Path, relative: str, label: str, kind: str) -> None:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError(f"{label} must be a non-empty POSIX-relative path")
    parts = PurePosixPath(relative)
    if parts.is_absolute() or ".." in parts.parts or relative in (".", ".."):
        raise ValueError(f"{label} escapes the task root")
    target = (base / Path(*parts.parts)).resolve()
    if target != base and base not in target.parents:
        raise ValueError(f"{label} escapes the task root")
    if kind == "file" and not target.is_file():
        raise ValueError(f"{label} not found: {relative}")
    if kind == "directory" and not target.is_dir():
        raise ValueError(f"{label} not found: {relative}")


def _budgets(spec: dict, identifier: str) -> dict:
    limits = {}
    for section in ("runtime", "execution"):
        settings = spec.get(section, {})
        if settings is None:
            settings = {}
        settings = _mapping(settings, f"{identifier}.{section}")
        for key, value in settings.items():
            if key in _INTEGER_LIMITS:
                if type(value) is not int or value <= 0:
                    raise ValueError(f"{identifier}.{section}.{key} must be a positive integer")
                limits[key] = value
            elif key in _NUMBER_LIMITS:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value < float("inf"):
                    raise ValueError(f"{identifier}.{section}.{key} must be a positive finite number")
                limits[key] = value
    return limits


def _v2_metadata(spec: dict, base: Path, identifier: str) -> None:
    _semver(spec.get("task_version"), f"{identifier}.task_version")
    _semver(spec.get("rubric_version"), f"{identifier}.rubric_version")

    cli = _mapping(spec.get("cli"), f"{identifier}.cli")
    command = cli.get("command")
    if command not in _CLI_COMMANDS:
        raise ValueError(f"{identifier}.cli.command must be evaluate, mutate or agent")
    handler = cli.get("handler")
    if command in ("evaluate", "mutate"):
        if not isinstance(handler, str) or not _HANDLER.fullmatch(handler):
            raise ValueError(f"{identifier}.cli.handler must name an AICB-9 evaluator")
    elif handler is not None:
        raise ValueError(f"{identifier}.cli.handler is not used for agent tasks")

    interfaces = _mapping(spec.get("interfaces"), f"{identifier}.interfaces")
    for key in ("input", "output"):
        _reference(base, interfaces.get(key), f"{identifier}.interfaces.{key}", "file")
    if interfaces.get("format") not in _OUTPUT_FORMATS:
        raise ValueError(f"{identifier}.interfaces.format is invalid")

    strategies = _mapping(spec.get("strategies"), f"{identifier}.strategies")
    groups = {}
    for key in ("supported", "planned"):
        values = strategies.get(key)
        if not isinstance(values, list) or any(not isinstance(v, str) or v not in _STRATEGIES for v in values):
            raise ValueError(f"{identifier}.strategies.{key} must be a list of S0-S3")
        if len(values) != len(set(values)):
            raise ValueError(f"{identifier}.strategies.{key} contains duplicates")
        groups[key] = set(values)
    if groups["supported"] & groups["planned"]:
        raise ValueError(f"{identifier}.strategies supported/planned overlap")

    fixture = _mapping(spec.get("fixture"), f"{identifier}.fixture")
    _semver(fixture.get("version"), f"{identifier}.fixture.version")
    if not isinstance(fixture.get("digest"), str) or not _DIGEST.fullmatch(fixture["digest"]):
        raise ValueError(f"{identifier}.fixture.digest must be a content-addressed tree SHA or SHA-256")
    _reference(base, spec.get("repository"), f"{identifier}.repository", "directory")

    evaluation = _mapping(spec.get("evaluation"), f"{identifier}.evaluation")
    for visibility in ("public", "private"):
        entry = _mapping(evaluation.get(visibility), f"{identifier}.evaluation.{visibility}")
        if entry.get("status") not in _STATUSES:
            raise ValueError(f"{identifier}.evaluation.{visibility}.status is invalid")
        if entry["status"] in ("implemented", "pilot") and not isinstance(entry.get("kind"), str):
            raise ValueError(f"{identifier}.evaluation.{visibility}.kind is required")

    scoring = _mapping(spec.get("scoring"), f"{identifier}.scoring")
    if not scoring or any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0
        for value in scoring.values()
    ):
        raise ValueError(f"{identifier}.scoring must contain non-negative numeric weights")
    if abs(sum(scoring.values()) - 100) > 1e-9:
        raise ValueError(f"{identifier}.scoring weights must sum to 100")


def load_registry(root: Path | None = None) -> list[dict]:
    """Load tasks, checking schema v2 strictly and preserving schema v1 inputs."""
    base = Path(root or task_root()).resolve()
    path = base / "registry.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"AICB-9 registry not found: {path}")
    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")) or {}, str(path))
    schema = raw.get("schema_version", 1)
    if type(schema) is not int or schema not in (1, 2):
        raise ValueError("Unsupported AICB-9 registry schema version")
    if schema == 2 and raw.get("benchmark") != "AICB-9":
        raise ValueError("Registry benchmark must be AICB-9")
    tasks = raw.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("Registry tasks must be a list")

    seen_ids, seen_slugs, seen_numbers = set(), set(), set()
    result = []
    for item in tasks:
        item = _mapping(item, "Registry task entry")
        identifier = item.get("id")
        if not isinstance(identifier, str) or not _TASK_ID.fullmatch(identifier):
            raise ValueError(f"Invalid AICB-9 task id: {identifier!r}")
        if identifier in seen_ids:
            raise ValueError(f"Duplicate AICB-9 task id: {identifier}")
        seen_ids.add(identifier)

        task_file = base / identifier / "task.yaml"
        if not task_file.is_file():
            raise ValueError(f"Missing task specification: {task_file}")
        spec = _mapping(yaml.safe_load(task_file.read_text(encoding="utf-8")) or {}, str(task_file))
        if spec.get("id") != identifier:
            raise ValueError(f"Task id mismatch in {task_file}")

        slug = spec.get("slug", item.get("slug"))
        if not isinstance(slug, str) or not _SLUG.fullmatch(slug):
            raise ValueError(f"Invalid slug for {identifier}")
        if "slug" in item and item["slug"] != slug:
            raise ValueError(f"Registry slug mismatch for {identifier}")
        if slug in seen_slugs:
            raise ValueError(f"Duplicate AICB-9 task slug: {slug}")
        seen_slugs.add(slug)

        number = spec.get("number")
        if number is not None:
            if type(number) is not int or number <= 0:
                raise ValueError(f"{identifier}.number must be a positive integer")
            if number in seen_numbers:
                raise ValueError(f"Duplicate AICB-9 task number: {number}")
            seen_numbers.add(number)
        if schema == 2:
            if not isinstance(item.get("category"), str) or not item["category"].strip():
                raise ValueError(f"Missing registry category for {identifier}")
            if type(item.get("api_required")) is not bool or type(spec.get("api_required")) is not bool:
                raise ValueError(f"{identifier}.api_required must be boolean")
            if item["api_required"] != spec["api_required"]:
                raise ValueError(f"Registry API requirement mismatch for {identifier}")
            _v2_metadata(spec, base, identifier)
        limits = _budgets(spec, identifier)
        merged = {**item, **spec, "directory": base / identifier}
        merged["schema_version"] = schema
        merged["task_version"] = spec.get("task_version", "0.0.0")
        merged["rubric_version"] = spec.get("rubric_version", "0.0.0")
        merged["budget_limits"] = limits
        if schema == 1:
            merged.setdefault("strategies", {"supported": [], "planned": []})
        result.append(merged)
    return result


def get_task(identifier: str | int, root: Path | None = None) -> dict:
    for task in load_registry(root):
        if identifier in (task["id"], task.get("slug"), task.get("number")):
            return task
    raise ValueError(f"Unknown AICB-9 task {identifier!r}")
