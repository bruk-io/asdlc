#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# ///
"""Summarise what one Claude run cost, from claude-code-action's execution file (spec R29).

The execution file is the run's messages as a JSON array; the last `result` message
carries the totals. The summary is Markdown, written for a job summary. Runs on a
subscription still report the cost at API prices, so usage stays comparable.

Usage: review_cost.py <execution file>
"""

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


ERROR_TEXT_LIMIT = 500


def _error_lines(result: Mapping[str, object]) -> list[str]:
    """Say why a run failed, since the action prints only a sanitised summary."""
    if not result.get("is_error"):
        return []
    errors = result.get("errors")
    text = str(result.get("result") or "").strip() or (
        "; ".join(str(e) for e in errors) if isinstance(errors, list) else ""
    )
    if not text:
        return ["- The run ended in an error, and the execution file gives no reason.", ""]
    shortened = text if len(text) <= ERROR_TEXT_LIMIT else text[:ERROR_TEXT_LIMIT] + "..."
    return [f"- The run ended in an error: {shortened}", ""]


def summarise(messages: Sequence[Mapping[str, object]]) -> str:
    """The cost table for one run, or a line saying why there is none."""
    results = [m for m in messages if m.get("type") == "result"]
    if not results:
        return "## Review cost\n\nNo result message in the execution file, so the run's cost is unknown.\n"
    result = results[-1]
    lines = [
        "## Review cost",
        "",
        *_error_lines(result),
        f"- Cost at API prices: ${float(result.get('total_cost_usd') or 0):.4f}",
        f"- Duration: {int(result.get('duration_ms') or 0) / 1000:.0f}s",
        f"- Turns: {result.get('num_turns', 'unknown')}",
        "",
        "| Model | Input tokens | Output tokens | Cache read | Cache write | Cost |",
        "|---|---|---|---|---|---|",
    ]
    usage = result.get("modelUsage") or {}
    for model, numbers in sorted(usage.items()):  # type: ignore[union-attr]
        lines.append(
            f"| {model} | {numbers.get('inputTokens', 0)} | {numbers.get('outputTokens', 0)} "
            f"| {numbers.get('cacheReadInputTokens', 0)} | {numbers.get('cacheCreationInputTokens', 0)} "
            f"| ${float(numbers.get('costUSD', 0)):.4f} |"
        )
    if not usage:
        lines.append("| (no per-model usage reported) | | | | | |")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[1]:
        print("## Review cost\n\nThe review produced no execution file, so the run's cost is unknown.")
        return 0
    path = Path(argv[1])
    try:
        messages = json.loads(path.read_text())
    except OSError, json.JSONDecodeError:
        print(f"## Review cost\n\nCould not read the execution file at `{path}`, so the run's cost is unknown.")
        return 0
    print(summarise(messages if isinstance(messages, list) else []), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
