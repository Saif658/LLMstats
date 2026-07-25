#!/usr/bin/env python3
"""Sync free models from OpenRouter, Groq, and Mistral into benchmark/test_models.py.

Called by a weekly GitHub Action. Fetches model lists from each provider's API,
diffs against the current catalog in test_models.py, and rewrites the file to
add new models and remove stale ones. Slots new models alternately into
GROUP1/GROUP2. A single commit covers all three providers.
"""

import ast
import json
import os
import sys
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEST_MODELS = SCRIPT_DIR / "test_models.py"
OPENROUTER_API = "https://openrouter.ai/api/v1/models"
GROQ_API = "https://api.groq.com/openai/v1/models"
MISTRAL_API = "https://api.mistral.ai/v1/models"


# ─── Fetch helpers ────────────────────────────────────────────────────────

def fetch_openrouter_free() -> set[str]:
    """Fetch free text-in/text-out model IDs from OpenRouter.

    A model is free when its pricing is zero, and is text-in/text-out
    when its architecture.output_modalities is exactly ``["text"]``.
    Uses ``model["id"]`` from the API response as-is.
    """
    req = urllib.request.Request(
        OPENROUTER_API,
        headers={"User-Agent": "LLMstats/1.0 (+https://github.com/Saif658/LLMstats)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    free = set()
    for model in data.get("data", []):
        pricing = model.get("pricing", {})
        if not (pricing.get("prompt") == "0" and pricing.get("completion") == "0"):
            continue
        arch = model.get("architecture")
        if arch is not None and arch.get("output_modalities", []) != ["text"]:
            continue
        free.add(model["id"])
    return free


def fetch_groq_models(api_key: str | None = None) -> set[str]:
    """Fetch text-chat model IDs from Groq, excluding audio/classification models."""
    if not api_key:
        print("  (GROQ_API_KEY not set — skipping)", flush=True)
        return set()
    req = urllib.request.Request(
        GROQ_API,
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "LLMstats/1.0 (+https://github.com/Saif658/LLMstats)",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    excluded_tokens = ("whisper", "prompt-guard", "moderation")
    result = set()
    for model in data.get("data", []):
        mid = model["id"]
        lowered = mid.lower()
        if any(token in lowered for token in excluded_tokens):
            continue
        result.add(mid)
    return result


def fetch_mistral_models(api_key: str | None = None) -> set[str]:
    """Fetch text-chat model IDs from Mistral, excluding non-chat types.

    Filters out ocr/voxtral (audio), embed, moderation, and fine-tuned (ft:)
    model ids. Keeps the same eligible set used in test_models.py.
    """
    if not api_key:
        print("  (MISTRAL_API_KEY not set — skipping)", flush=True)
        return set()
    req = urllib.request.Request(
        MISTRAL_API,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    excluded_substrings = ("ocr", "voxtral", "embed", "moderation")
    result = set()
    for model in data.get("data", []):
        mid = model["id"]
        if mid.startswith("ft:"):
            continue
        lowered = mid.lower()
        if any(token in lowered for token in excluded_substrings):
            continue
        result.add(mid)
    return result


# ─── AST parsing ──────────────────────────────────────────────────────────

def parse_or_dict(assign_node: ast.Assign) -> dict[str, list[str]]:
    """Parse OR_MODELS_BY_PROVIDER from an Assign AST node."""
    result: dict[str, list[str]] = {}
    for key_node, val_node in zip(assign_node.value.keys, assign_node.value.values):
        result[key_node.value] = [elt.value for elt in val_node.elts]
    return result


def parse_simple_list(node: ast.Assign | ast.AnnAssign) -> list[str]:
    """Parse a flat list[str] AST node."""
    return [elt.value for elt in node.value.elts]


def parse_group_list(annassign_node: ast.AnnAssign) -> list[tuple[str, str]]:
    """Parse GROUP1/GROUP2 list from an AnnAssign AST node."""
    result: list[tuple[str, str]] = []
    for elt in annassign_node.value.elts:
        result.append((elt.elts[0].value, elt.elts[1].value))
    return result


# ─── Formatting ───────────────────────────────────────────────────────────

def format_dict(data: dict[str, list[str]]) -> str:
    """Format OR_MODELS_BY_PROVIDER dict matching the existing style."""
    lines = []
    for key in data:
        val = data[key]
        if len(val) == 1:
            lines.append(f'    "{key}":\n        ["{val[0]}"],')
        else:
            inner = ",\n".join(f'            "{m}"' for m in val)
            lines.append(f'    "{key}":\n        [\n{inner},\n        ],')
    return "{\n" + "\n".join(lines) + "\n}"


def format_list(data: list[str]) -> str:
    """Format a flat list[str] matching existing style."""
    if not data:
        return "[]"
    items = ",\n".join(f'    "{m}"' for m in data)
    return f"[\n{items},\n]"


def format_group(models: list[tuple[str, str]]) -> str:
    """Format GROUP1/GROUP2 list with aligned provider column."""
    if not models:
        return "[]"
    max_len = max(len(m[0]) for m in models)
    pad_to = max_len + 2
    items = []
    for model_id, provider in models:
        padding = pad_to - len(model_id)
        items.append(f'    ("{model_id}",{" " * padding}"{provider}"),')
    return "[\n" + "\n".join(items) + "\n]"


# ─── Main ─────────────────────────────────────────────────────────────────

def main() -> int:
    # Fetch from all providers
    print("Fetching free models from OpenRouter...", flush=True)
    try:
        or_models = fetch_openrouter_free()
    except Exception as e:
        print(f"Error fetching OpenRouter models: {e}", file=sys.stderr)
        return 1
    print(f"  Found {len(or_models)} free models", flush=True)

    print("Fetching models from Groq...", flush=True)
    try:
        groq_models = fetch_groq_models(os.getenv("GROQ_API_KEY"))
    except Exception as e:
        print(f"Error fetching Groq models: {e}", file=sys.stderr)
        return 1
    if groq_models:
        print(f"  Found {len(groq_models)} chat models", flush=True)

    print("Fetching models from Mistral...", flush=True)
    try:
        mistral_models = fetch_mistral_models(os.getenv("MISTRAL_API_KEY"))
    except Exception as e:
        print(f"Error fetching Mistral models: {e}", file=sys.stderr)
        return 1
    if mistral_models:
        print(f"  Found {len(mistral_models)} chat models", flush=True)

    # Read and parse current file
    source = TEST_MODELS.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    # Locate AST nodes for all five sections
    or_node = groq_node = mistral_node = g1_node = g2_node = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    tid = target.id
                    if tid == "OR_MODELS_BY_PROVIDER":
                        or_node = node
                    elif tid == "GROQ_MODELS":
                        groq_node = node
                    elif tid == "MISTRAL_MODELS":
                        mistral_node = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            tid = node.target.id
            if tid == "GROUP1_MODELS":
                g1_node = node
            elif tid == "GROUP2_MODELS":
                g2_node = node

    if not all([or_node, groq_node, mistral_node, g1_node, g2_node]):
        print("Could not find required sections in test_models.py", file=sys.stderr)
        return 1

    # Parse current data structures from AST
    current_or_dict = parse_or_dict(or_node)
    current_groq = set(parse_simple_list(groq_node))
    current_mistral = set(parse_simple_list(mistral_node))
    g1_list = parse_group_list(g1_node)
    g2_list = parse_group_list(g2_node)

    # --- Compute diffs per provider ---

    current_or_free = {m for models in current_or_dict.values() for m in models}
    or_to_add = sorted(or_models - current_or_free)
    or_to_remove = current_or_free - or_models

    groq_to_add = sorted(groq_models - current_groq)
    groq_to_remove = current_groq - groq_models

    mistral_to_add = sorted(mistral_models - current_mistral)
    mistral_to_remove = current_mistral - mistral_models

    all_to_add = or_to_add + groq_to_add + mistral_to_add
    all_to_remove = or_to_remove | groq_to_remove | mistral_to_remove

    if not all_to_add and not all_to_remove:
        print("No changes needed — model list is up to date", flush=True)
        return 0

    print(f"\nOpenRouter +{len(or_to_add)} -{len(or_to_remove)} "
          f"| Groq +{len(groq_to_add)} -{len(groq_to_remove)} "
          f"| Mistral +{len(mistral_to_add)} -{len(mistral_to_remove)}",
          flush=True)
    for m in or_to_add:
        print(f"  + OR   {m}", flush=True)
    for m in groq_to_add:
        print(f"  + Groq {m}", flush=True)
    for m in mistral_to_add:
        print(f"  + Mist {m}", flush=True)
    for m in sorted(all_to_remove):
        print(f"  -      {m}", flush=True)

    # --- Determine which provider a model belongs to (for group tagging) ---

    fresh_or = (current_or_free - or_to_remove) | set(or_to_add)
    fresh_groq = (current_groq - groq_to_remove) | set(groq_to_add)
    fresh_mistral = (current_mistral - mistral_to_remove) | set(mistral_to_add)

    def provider_tag(model_id: str) -> str:
        if model_id in fresh_or:
            return "openrouter"
        if model_id in fresh_groq:
            return "groq"
        return "mistral"

    # --- Update OR_MODELS_BY_PROVIDER ---

    new_or_dict: dict[str, list[str]] = {}
    for key, models in current_or_dict.items():
        kept = [m for m in models if m not in or_to_remove]
        if kept:
            new_or_dict[key] = kept
    if or_to_add:
        new_or_dict["Auto-added"] = or_to_add

    # --- Update GROQ_MODELS (preserve existing order, append new) ---

    groq_list = parse_simple_list(groq_node)
    new_groq = [m for m in groq_list if m not in groq_to_remove]
    new_groq.extend(groq_to_add)

    # --- Update MISTRAL_MODELS (preserve existing order, append new) ---

    mistral_list = parse_simple_list(mistral_node)
    new_mistral = [m for m in mistral_list if m not in mistral_to_remove]
    new_mistral.extend(mistral_to_add)

    # --- Update GROUP1 / GROUP2 ---

    g1_list = [(m, p) for m, p in g1_list if m not in all_to_remove]
    g2_list = [(m, p) for m, p in g2_list if m not in all_to_remove]

    all_new_sorted = sorted(all_to_add)
    for i, m in enumerate(all_new_sorted):
        tag = provider_tag(m)
        if i % 2 == 0:
            g1_list.append((m, tag))
        else:
            g2_list.append((m, tag))

    # --- Rewrite file (bottom-to-top to preserve line numbers) ---

    new_lines = list(lines)

    new_g2 = f"GROUP2_MODELS: list[tuple[str, str]] = {format_group(g2_list)}\n"
    new_lines[g2_node.lineno - 1 : g2_node.end_lineno] = [new_g2]

    new_g1 = f"GROUP1_MODELS: list[tuple[str, str]] = {format_group(g1_list)}\n"
    new_lines[g1_node.lineno - 1 : g1_node.end_lineno] = [new_g1]

    new_mistral_str = f"MISTRAL_MODELS = {format_list(new_mistral)}\n"
    new_lines[mistral_node.lineno - 1 : mistral_node.end_lineno] = [new_mistral_str]

    new_groq_str = f"GROQ_MODELS = {format_list(new_groq)}\n"
    new_lines[groq_node.lineno - 1 : groq_node.end_lineno] = [new_groq_str]

    new_or = f"OR_MODELS_BY_PROVIDER = {format_dict(new_or_dict)}\n"
    new_lines[or_node.lineno - 1 : or_node.end_lineno] = [new_or]

    TEST_MODELS.write_text("".join(new_lines), encoding="utf-8")
    print(f"\nUpdated {TEST_MODELS}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())