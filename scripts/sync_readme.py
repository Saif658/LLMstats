#!/usr/bin/env python3
"""Sync README.md model tables and derived counts with benchmark/test_models.py.

Reads the model catalog out of test_models.py with the `ast` module (never
imports or executes it), then rewrites the marker-delimited model sections in
README.md plus the counts computed from that data. Note text is preserved for
models that stay in the catalog; models new to the catalog get "New model".
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "benchmark" / "test_models.py"
README = ROOT / "README.md"

# Model-id substrings that mean "not a chat model". Mirrors the filters in
# benchmark/sync_all_models.py, plus orpheus (speech/TTS) and fim
# (fill-in-the-middle code completion, which isn't chat).
NON_CHAT_SUBSTRINGS = (
    "orpheus",
    "whisper",
    "prompt-guard",
    "embed",
    "voxtral",
    "ocr",
    "moderation",
    "fim",
)

# OpenRouter model-org prefix -> display name for the Upstream column.
# Falls back to the raw org segment for prefixes not listed here.
UPSTREAM_LABELS = {
    "nvidia": "NVIDIA",
    "google": "Google",
    "cohere": "Cohere",
    "poolside": "Poolside",
    "stealth": "Stealth",
    "thinkingmachines": "Thinking Machines",
}

# The section-summary "upstream providers" numerology reproduces the original
# "14+": 11 OpenRouter upstreams + 3 gateways (OpenRouter, Groq, Mistral).
GATEWAYS = 3

MARKERS = {
    "openrouter": (
        "<!-- OPENROUTER_MODELS:START -->",
        "<!-- OPENROUTER_MODELS:END -->",
    ),
    "groq": ("<!-- GROQ_MODELS:START -->", "<!-- GROQ_MODELS:END -->"),
    "mistral": (
        "<!-- MISTRAL_MODELS:START -->",
        "<!-- MISTRAL_MODELS:END -->",
    ),
}

INTRO_RE = re.compile(
    r"\*\*LLMstats\*\* automatically benchmarks \*\*\d+ free-tier models\*\* "
    r"roughly every 3 hours — \*\*\d+ served by "
    r"\[OpenRouter\]\(https://openrouter\.ai/\) \(the unified router, "
    r"\d+ upstream providers\), \d+ by \[Groq\]\(https://groq\.com/\) "
    r"\(the LPU cloud\), and \d+ by \[Mistral\]\(https://mistral\.ai/\) "
    r"\(Experiment tier\)\*\*"
)

SUMMARY_RE = re.compile(
    r"<summary><b>\d+ models across 3 gateways, \d+\+ upstream providers"
    r"</b</summary>"
)

DIAGRAM_RE = re.compile(r"(\d+) models \(mixed\)")


def load_catalog() -> dict[str, object]:
    """Fetch the catalog lists out of test_models.py without importing it."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    wanted = {
        "OR_MODELS_BY_PROVIDER",
        "GROQ_MODELS",
        "MISTRAL_MODELS",
        "GROUP1_MODELS",
        "GROUP2_MODELS",
    }
    values: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            candidates = [node.target.id]
        elif isinstance(node, ast.Assign):
            candidates = [t.id for t in node.targets if isinstance(t, ast.Name)]
        else:
            continue
        for name in candidates:
            if name in wanted:
                values[name] = ast.literal_eval(node.value)
    missing = wanted - values.keys()
    if missing:
        sys.exit(
            f"sync_readme: catalog vars missing from {SOURCE}: {sorted(missing)}"
        )
    return values


def is_chat(model_id: str) -> bool:
    lowered = model_id.lower()
    return not any(token in lowered for token in NON_CHAT_SUBSTRINGS)


def upstream_label(model_id: str) -> str:
    org = model_id.split("/", 1)[0] if "/" in model_id else model_id
    return UPSTREAM_LABELS.get(org, org)


def openrouter_rows(by_provider: dict[str, list[str]]) -> list[tuple[str, str]]:
    """(upstream, model) rows for the OpenRouter table, deduped and grouped."""
    seen: set[str] = set()
    ordered: list[str] = []
    grouped: dict[str, list[str]] = {}
    for models in by_provider.values():
        for model in models:
            if model in seen:
                continue
            seen.add(model)
            if not is_chat(model):
                continue
            label = upstream_label(model)
            if label not in grouped:
                grouped[label] = []
                ordered.append(label)
            grouped[label].append(model)
    return [(label, model) for label in ordered for model in grouped[label]]


def chat_models(model_ids: list[str]) -> list[str]:
    """Deduped, order-preserving subset that isn't a non-chat model."""
    seen: set[str] = set()
    result: list[str] = []
    for model in model_ids:
        if model in seen:
            continue
        seen.add(model)
        if is_chat(model):
            result.append(model)
    return result


def extract_notes(region: str) -> dict[str, str]:
    """Existing notes keyed by model id, read from the current table rows."""
    notes: dict[str, str] = {}
    for line in region.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        model_index = None
        model_cell = ""
        for i, cell in enumerate(cells):
            if cell.startswith("`") and cell.endswith("`"):
                model_index = i
                model_cell = cell
                break
        if model_index is None:
            continue
        model = model_cell.strip("`")
        note = cells[model_index + 1].strip() if model_index + 1 < len(cells) else ""
        if model and note:
            notes[model] = note
    return notes


def replace_region(text: str, start: str, end: str, content: str) -> str:
    """Replace everything between the two marker lines (markers kept)."""
    start_at = text.find(start)
    if start_at == -1:
        sys.exit(f"sync_readme: missing marker {start!r} in {README.name}")
    end_at = text.find(end, start_at + len(start))
    if end_at == -1:
        sys.exit(f"sync_readme: missing marker {end!r} in {README.name}")
    return (
        text[: start_at + len(start)]
        + "\n"
        + content.strip("\n")
        + "\n"
        + text[end_at:]
    )


def build_openrouter_section(
    rows: list[tuple[str, str]], notes: dict[str, str]
) -> str:
    upstream_count = len({label for label, _ in rows})
    lines = [
        f"### 🟣 OpenRouter · {len(rows)} models · {upstream_count} upstream providers",
        "| Upstream | Model | Note |",
        "|----------|-------|------|",
    ]
    for label, model in rows:
        lines.append(
            f"| **{label}** | `{model}` | {notes.get(model, 'New model')} |"
        )
    return "\n".join(lines)


def build_simple_section(
    heading: str, models: list[str], notes: dict[str, str]
) -> str:
    lines = [heading, "| Model | Note |", "|-------|------|"]
    for model in models:
        lines.append(f"| `{model}` | {notes.get(model, 'New model')} |")
    return "\n".join(lines)


def main() -> int:
    catalog = load_catalog()
    or_rows = openrouter_rows(catalog["OR_MODELS_BY_PROVIDER"])
    groq_models = chat_models(catalog["GROQ_MODELS"])
    mistral_models = chat_models(catalog["MISTRAL_MODELS"])

    total = len(or_rows) + len(groq_models) + len(mistral_models)
    or_upstreams = len({label for label, _ in or_rows})
    group1_size = len(catalog["GROUP1_MODELS"])
    group2_size = len(catalog["GROUP2_MODELS"])

    text = README.read_text(encoding="utf-8")

    notes_by_table: dict[str, dict[str, str]] = {}
    for key, (start, end) in MARKERS.items():
        start_at = text.find(start)
        if start_at == -1:
            sys.exit(f"sync_readme: missing marker {start!r} in {README.name}")
        end_at = text.find(end, start_at + len(start))
        if end_at == -1:
            sys.exit(f"sync_readme: missing marker {end!r} in {README.name}")
        notes_by_table[key] = extract_notes(text[start_at + len(start) : end_at])

    new_text = text
    new_text = replace_region(
        new_text,
        *MARKERS["openrouter"],
        build_openrouter_section(or_rows, notes_by_table["openrouter"]),
    )
    new_text = replace_region(
        new_text,
        *MARKERS["groq"],
        build_simple_section(
            f"### 🟠 Groq · {len(groq_models)} chat models",
            groq_models,
            notes_by_table["groq"],
        ),
    )
    new_text = replace_region(
        new_text,
        *MARKERS["mistral"],
        build_simple_section(
            f"### 🔵 Mistral · {len(mistral_models)} chat models (Experiment tier)",
            mistral_models,
            notes_by_table["mistral"],
        ),
    )

    new_text, n = INTRO_RE.subn(
        f"**LLMstats** automatically benchmarks **{total} free-tier models** "
        f"roughly every 3 hours — **{len(or_rows)} served by "
        f"[OpenRouter](https://openrouter.ai/) (the unified router, "
        f"{or_upstreams} upstream providers), {len(groq_models)} by "
        f"[Groq](https://groq.com/) (the LPU cloud), and "
        f"{len(mistral_models)} by [Mistral](https://mistral.ai/) "
        f"(Experiment tier)**",
        new_text,
    )
    if n != 1:
        sys.exit(f"sync_readme: intro count line matched {n} times (expected 1)")

    new_text, n = SUMMARY_RE.subn(
        f"<summary><b>{total} models across 3 gateways, "
        f"{or_upstreams + GATEWAYS}+ upstream providers</b</summary>",
        new_text,
    )
    if n != 1:
        sys.exit(f"sync_readme: summary count line matched {n} times (expected 1)")

    group_sizes = iter([group1_size, group2_size])

    def _diagram_repl(_match: re.Match[str]) -> str:
        try:
            size = next(group_sizes)
        except StopIteration:
            sys.exit("sync_readme: too many diagram group lines found")
        return f"{size:>2} models (mixed)"

    new_text, n = DIAGRAM_RE.subn(_diagram_repl, new_text)
    if n != 2:
        sys.exit(f"sync_readme: diagram group lines matched {n} times (expected 2)")

    if new_text == text:
        print("README.md already up to date")
        return 0

    # Preserve the file's existing line endings (CRLF on Windows checkouts).
    if b"\r\n" in README.read_bytes():
        new_text = new_text.replace("\n", "\r\n")
    README.write_text(new_text, encoding="utf-8", newline="")
    print(
        f"README.md updated: {total} models (OpenRouter {len(or_rows)} / "
        f"Groq {len(groq_models)} / Mistral {len(mistral_models)}), "
        f"{or_upstreams} OpenRouter upstreams, groups {group1_size}/{group2_size}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())