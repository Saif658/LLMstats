#!/usr/bin/env python3
"""Sync OpenRouter free models into benchmark/test_models.py.

Called by a weekly GitHub Action. Fetches OpenRouter's /api/v1/models,
finds free models (pricing = 0), and rewrites the model catalog in
test_models.py to add new models and remove stale ones.
"""

import ast
import json
import sys
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEST_MODELS = SCRIPT_DIR / "test_models.py"
OPENROUTER_API = "https://openrouter.ai/api/v1/models"


def fetch_free_models() -> set[str]:
    """Fetch free text-in/text-out model IDs from OpenRouter.

    A model is free when its pricing is zero, and is text-in/text-out
    when its architecture.output_modalities is exactly ``["text"]``.
    Uses ``model["id"]`` from the API response as-is — no suffix
    manipulation.
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


def parse_or_dict(assign_node: ast.Assign) -> dict[str, list[str]]:
    """Parse OR_MODELS_BY_PROVIDER from an Assign AST node."""
    result: dict[str, list[str]] = {}
    for key_node, val_node in zip(assign_node.value.keys, assign_node.value.values):
        result[key_node.value] = [elt.value for elt in val_node.elts]
    return result


def parse_group_list(annassign_node: ast.AnnAssign) -> list[tuple[str, str]]:
    """Parse GROUP1/GROUP2 list from an AnnAssign AST node."""
    result: list[tuple[str, str]] = []
    for elt in annassign_node.value.elts:
        result.append((elt.elts[0].value, elt.elts[1].value))
    return result


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


def main() -> int:
    print("Fetching free models from OpenRouter...", flush=True)
    try:
        api_free = fetch_free_models()
    except Exception as e:
        print(f"Error fetching models: {e}", file=sys.stderr)
        return 1
    print(f"Found {len(api_free)} free models", flush=True)

    # Read and parse current file
    source = TEST_MODELS.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    # Locate AST nodes
    or_node = g1_node = g2_node = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "OR_MODELS_BY_PROVIDER":
                    or_node = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "GROUP1_MODELS":
                g1_node = node
            elif node.target.id == "GROUP2_MODELS":
                g2_node = node

    if not all([or_node, g1_node, g2_node]):
        print("Could not find required sections in test_models.py", file=sys.stderr)
        return 1

    # Parse current data structures
    current_dict = parse_or_dict(or_node)
    g1_list = parse_group_list(g1_node)
    g2_list = parse_group_list(g2_node)

    # Compute diff
    current_free = {m for models in current_dict.values() for m in models}
    to_add = sorted(api_free - current_free)
    to_remove = current_free - api_free

    if not to_add and not to_remove:
        print("No changes needed - model list is up to date", flush=True)
        return 0

    print(f"Models to add: {len(to_add)}", flush=True)
    print(f"Models to remove: {len(to_remove)}", flush=True)
    for m in to_add:
        print(f"  + {m}", flush=True)
    for m in to_remove:
        print(f"  - {m}", flush=True)

    # Update OR_MODELS_BY_PROVIDER
    new_dict: dict[str, list[str]] = {}
    for key, models in current_dict.items():
        kept = [m for m in models if m not in to_remove]
        if kept:
            new_dict[key] = kept
    if to_add:
        new_dict["Auto-added"] = to_add

    # Update GROUP1/GROUP2
    g1_list = [(m, p) for m, p in g1_list if m not in to_remove]
    g2_list = [(m, p) for m, p in g2_list if m not in to_remove]
    for i, m in enumerate(to_add):
        if i % 2 == 0:
            g1_list.append((m, "openrouter"))
        else:
            g2_list.append((m, "openrouter"))

    # Rewrite file (bottom-to-top to preserve line numbers)
    new_lines = list(lines)

    new_g2 = f"GROUP2_MODELS: list[tuple[str, str]] = {format_group(g2_list)}\n"
    new_lines[g2_node.lineno - 1 : g2_node.end_lineno] = [new_g2]

    new_g1 = f"GROUP1_MODELS: list[tuple[str, str]] = {format_group(g1_list)}\n"
    new_lines[g1_node.lineno - 1 : g1_node.end_lineno] = [new_g1]

    new_or = f"OR_MODELS_BY_PROVIDER = {format_dict(new_dict)}\n"
    new_lines[or_node.lineno - 1 : or_node.end_lineno] = [new_or]

    TEST_MODELS.write_text("".join(new_lines), encoding="utf-8")
    print(f"Updated {TEST_MODELS}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())