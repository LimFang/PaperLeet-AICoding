"""Versioned constants and canonical serialization for benchmark runs."""
import hashlib
import json

BENCHMARK_PROTOCOL_VERSION = "0.1"
RUN_REPORT_SCHEMA_VERSION = "1.0"
RUNNER_VERSION = "0.1.0"
STRATEGY_VERSION = "0.1.0"
PROMPT_TEMPLATE_VERSION = "1"
OUTPUT_SCHEMA_VERSION = "1"
STRATEGY_IDS = ("S0", "S1", "S2", "S3")
RUN_STATUSES = ("succeeded", "failed", "timed_out", "budget_exceeded", "cancelled")


def canonical_json(value) -> str:
    """Stable UTF-8 JSON representation for hashes and artifact digests."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_digest(value) -> str:
    """Return a prefixed SHA-256 digest for text or a JSON-serializable object."""
    payload = value.encode("utf-8") if isinstance(value, str) else canonical_json(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()
