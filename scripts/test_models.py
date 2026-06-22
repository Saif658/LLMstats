#!/usr/bin/env python3

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db_utils import write_run

REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "300"))
PROMPT = "Write a Python function that checks if a number is prime and returns True or False"

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = SCRIPT_DIR / "results.json"

# ─── Provider config ──────────────────────────────────────────────────────────
# Each provider exposes an OpenAI-compatible /chat/completions endpoint.
PROVIDERS: dict[str, dict[str, Any]] = {
    "openrouter": {
        "base": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "extra_headers": {
            "HTTP-Referer": "https://github.com/Saif658/LLMstats",
            "X-Title": "LLMstats",
        },
    },
    "groq": {
        "base": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "extra_headers": {},
    },
}

# ─── Model catalog ────────────────────────────────────────────────────────────
# Curated free-tier models so cron runs don't burn through paid credits.
# OpenRouter's mid-2026 free (:free-suffixed) catalog is narrow; verified
# against https://openrouter.ai/api/v1/models
OPENROUTER_FREE_MODELS = [
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nvidia/nemotron-3.5-content-safety:free",
    "poolside/laguna-xs.2:free",
    "poolside/laguna-m.1:free",
]

# Verified-valid Groq chat models in mid-2026 (whisper + prompt-guard skipped
# — those are audio / classification, not chat).
GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "qwen/qwen3-32b",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-120b",
    "allam-2-7b",
]

# (model_id, provider_name) pairs joined for convenience elsewhere.
ALL_MODELS: list[tuple[str, str]] = (
    [(m, "openrouter") for m in OPENROUTER_FREE_MODELS]
    + [(m, "groq") for m in GROQ_MODELS]
)

# Split roughly in half for parallel matrix jobs.
def _split_models() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    half = len(ALL_MODELS) // 2
    return ALL_MODELS[:half], ALL_MODELS[half:]


GROUP1_MODELS, GROUP2_MODELS = _split_models()


# ─── CLI selection ────────────────────────────────────────────────────────────
def selected_models() -> list[tuple[str, str]]:
    group = os.getenv("MODEL_GROUP", "all").lower()
    if group == "group1":
        return GROUP1_MODELS
    if group == "group2":
        return GROUP2_MODELS
    return ALL_MODELS


# ─── Result helpers ───────────────────────────────────────────────────────────
def failure_result(model: str, provider: str, error: str) -> dict[str, Any]:
    return {
        "model": model,
        "provider": provider,
        "success": False,
        "error": error,
        "responseTime": None,
        "tokensGenerated": None,
        "totalTokens": None,
        "response": None,
    }


# ─── Response parsing ─────────────────────────────────────────────────────────
def normalize_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ─── API call ─────────────────────────────────────────────────────────────────
def call_model(model: str, provider_name: str, prompt: str) -> dict[str, Any]:
    provider = PROVIDERS[provider_name]
    api_key = os.getenv(provider["key_env"], "")
    if not api_key:
        return failure_result(model, provider_name, f"{provider['key_env']} not set")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 500,
        "stream": False,
    }
    body = json.dumps(payload).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "LLMstats/1.0 (+https://github.com/Saif658/LLMstats)",
    }
    headers.update(provider.get("extra_headers", {}))

    request = urllib.request.Request(
        f"{provider['base']}/chat/completions",
        data=body,
        method="POST",
        headers=headers,
    )

    started = time.perf_counter()
    raw_body = ""
    status_code = 0

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            status_code = response.status
            raw_body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status_code = getattr(exc, "code", 0) or 0
        raw_body = exc.read().decode("utf-8", errors="replace")
    except TimeoutError:
        return failure_result(model, provider_name, f"Request timed out after {REQUEST_TIMEOUT_SECONDS}s")
    except Exception as exc:
        return failure_result(model, provider_name, f"Request failed: {exc}")

    response_time = int((time.perf_counter() - started) * 1000)

    if not raw_body.strip():
        return failure_result(model, provider_name, "Empty response from API")

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        snippet = raw_body[:200].replace("\n", " ")
        print(f"  [debug] raw body ({len(raw_body)} bytes): {snippet!r}", file=sys.stderr)
        return {
            "model": model,
            "provider": provider_name,
            "success": False,
            "error": f"Invalid JSON response: {exc.msg} at line {exc.lineno} column {exc.colno}",
            "responseTime": response_time,
            "tokensGenerated": None,
            "totalTokens": None,
            "response": raw_body,
        }

    error_obj = data.get("error")
    error_message = ""
    if isinstance(error_obj, dict):
        error_message = str(error_obj.get("message") or "").strip()
    elif isinstance(error_obj, str):
        error_message = error_obj.strip()

    if status_code >= 400:
        if not error_message:
            error_message = f"HTTP {status_code} returned by API"
        else:
            error_message = f"HTTP {status_code}: {error_message}"
        return failure_result(model, provider_name, error_message)

    if error_message:
        return failure_result(model, provider_name, error_message)

    choices = data.get("choices")
    content = ""
    if isinstance(choices, list) and choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message")
            if isinstance(message, dict):
                content = normalize_content(message.get("content"))

    if not content.strip():
        return failure_result(model, provider_name, "No content in response")

    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    completion_tokens = to_int(usage.get("completion_tokens"))
    total_tokens = to_int(usage.get("total_tokens"))

    return {
        "model": model,
        "provider": provider_name,
        "success": True,
        "responseTime": response_time,
        "tokensGenerated": completion_tokens,
        "totalTokens": total_tokens,
        "response": content,
        "error": None,
    }


# ─── Output assembly ──────────────────────────────────────────────────────────
def compile_output(timestamp: str, prompt: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [item for item in results if item.get("success")]
    success_count = len(successful)
    total_count = len(results)

    if successful:
        fastest = min(
            successful,
            key=lambda item: item.get("responseTime")
            if isinstance(item.get("responseTime"), int)
            else float("inf"),
        )
        fastest_model = fastest.get("model", "N/A")
        fastest_time = fastest.get("responseTime", 0) or 0
    else:
        fastest_model = "N/A"
        fastest_time = 0

    return {
        "timestamp": timestamp,
        "prompt": prompt,
        "models": results,
        "summary": {
            "successCount": success_count,
            "totalModels": total_count,
            "fastestModel": fastest_model,
            "fastestTime": fastest_time,
        },
    }


def update_history(new_run: dict[str, Any]) -> None:
    write_run(new_run)
    print(f"History updated: {str(SCRIPT_DIR.parent / 'history.db')}")


# ─── Entry point ──────────────────────────────────────────────────────────────
def main() -> int:
    missing = [p["key_env"] for p in PROVIDERS.values() if not os.getenv(p["key_env"], "")]
    if missing:
        print(f"Error: missing API keys: {', '.join(missing)}", file=sys.stderr)
        return 1

    models = selected_models()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    group_label = f" (Group: {os.getenv('MODEL_GROUP', 'all')})"
    print(f"Starting LLMstats Benchmarks{group_label}...")
    print(f"Timestamp: {timestamp}")
    print(f"Testing {len(models)} models across {len({p for _, p in models})} providers...")
    print()

    results: list[dict[str, Any]] = []
    for model, provider in models:
        print(f"Testing: [{provider}] {model}")
        result = call_model(model, provider, PROMPT)
        if result.get("success"):
            print(
                f"  ✓ Success ({result['responseTime']}ms, {result.get('tokensGenerated', 0)} tokens)"
            )
        else:
            print(f"  ✗ Failed: {result.get('error') or 'Unknown error'}")
        results.append(result)
        time.sleep(0.5)

    print()
    print("Compiling results...")

    final_json = compile_output(timestamp, PROMPT, results)
    OUTPUT_FILE.write_text(json.dumps(final_json, indent=2), encoding="utf-8")

    success_count = final_json["summary"]["successCount"]
    total_count = final_json["summary"]["totalModels"]
    print(f"Results saved to {OUTPUT_FILE.name}")
    print(f"Summary: {success_count}/{total_count} successful")

    if os.getenv("MODEL_GROUP", "all").lower() == "all":
        update_history(final_json)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
