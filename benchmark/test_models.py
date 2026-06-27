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
DEFAULT_MAX_TOKENS = 500
PROMPT = "Write a Python function that checks if a number is prime and returns True or False"

# Per-model max_tokens overrides — reasoning-heavy models burn 500 tokens on
# internal thinking and return empty content. Raise budget for those.
MODEL_MAX_TOKENS_OVERRIDES: dict[str, int] = {
    "liquid/lfm-2.5-1.2b-thinking:free": 2000,
    "nvidia/nemotron-nano-9b-v2:free": 2000,
    "cohere/north-mini-code:free": 2000,
    "poolside/laguna-m.1:free": 2000,
}

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
    "mistral": {
        "base": "https://api.mistral.ai/v1",
        "key_env": "MISTRAL_API_KEY",
        "extra_headers": {},
    },
}

# ─── Model catalog ────────────────────────────────────────────────────────────
# Curated free-tier models so cron runs don't burn through paid credits.
# OpenRouter's free (:free-suffixed) catalog verified against
# https://openrouter.ai/api/v1/models — covers 16 distinct upstream providers.
OR_MODELS_BY_PROVIDER = {
    "OpenRouter (their own gateway)":
        ["openrouter/free", "openrouter/owl-alpha"],
    "OpenAI":
        ["openai/gpt-oss-120b:free", "openai/gpt-oss-20b:free"],
    "Meta":
        ["meta-llama/llama-3.3-70b-instruct:free", "meta-llama/llama-3.2-3b-instruct:free"],
    "NVIDIA":
        [
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "nvidia/nemotron-3-nano-30b-a3b:free",
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "nvidia/nemotron-nano-12b-v2-vl:free",
            "nvidia/nemotron-nano-9b-v2:free",
            "nvidia/nemotron-3.5-content-safety:free",
        ],
    "Qwen":
        ["qwen/qwen3-coder:free", "qwen/qwen3-next-80b-a3b-instruct:free"],
    "Google":
        ["google/gemma-4-26b-a4b-it:free"],
    "Nous":
        ["nousresearch/hermes-3-llama-3.1-405b:free"],
    "Poolside":
        ["poolside/laguna-m.1:free", "poolside/laguna-xs.2:free"],
    "Cohere":
        ["cohere/north-mini-code:free"],
    "Liquid":
        ["liquid/lfm-2.5-1.2b-instruct:free", "liquid/lfm-2.5-1.2b-thinking:free"],
    "Cognitive Computations":
        ["cognitivecomputations/dolphin-mistral-24b-venice-edition:free"],
}
OPENROUTER_FREE_MODELS = [m for ms in OR_MODELS_BY_PROVIDER.values() for m in ms]

# Verified-valid Groq chat models in mid-2026 (whisper + prompt-guard skipped
# — those are audio / classification, not chat).
GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "qwen/qwen3-32b",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-safeguard-20b",
    "groq/compound",
    "groq/compound-mini",
    "allam-2-7b",
]


def fetch_mistral_models(api_key: str) -> list[str]:
    """List text-chat models available from Mistral's API.

    Filters out ocr/voxtral (audio), embed, moderation, and fine-tuned (ft:)
    model ids. Keeps Small/Medium/Large/Codestral/Devstral/Magistral/Ministral
    and open-* variants — all eligible for the same shared Experiment-tier cap.
    """
    req = urllib.request.Request(
        "https://api.mistral.ai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    excluded_substrings = ("ocr", "voxtral", "embed", "moderation")

    def keep(model_id: str) -> bool:
        if model_id.startswith("ft:"):
            return False
        lowered = model_id.lower()
        return not any(token in lowered for token in excluded_substrings)

    return [m["id"] for m in data.get("data", []) if keep(m["id"])]


# Mistral text-chat models — Experiment tier covers the entire chat catalog
# under one shared rate limit (verified against api.mistral.ai/v1/models on
# 2026-06-27). Snapshot rather than fetching every run so benchmark history
# stays comparable run-to-run, the same reasoning as NVIDIA.
MISTRAL_MODELS = [
    "mistral-large-latest",
    "mistral-medium-latest",
    "mistral-small-latest",
    "mistral-tiny-latest",
    "ministral-8b-latest",
    "ministral-3b-latest",
    "magistral-medium-latest",
    "magistral-small-latest",
    "codestral-latest",
    "devstral-latest",
    "devstral-small-latest",
    "open-mistral-7b",
    "open-mixtral-8x7b",
    "open-mixtral-8x22b",
    "mistral-saba-latest",
    "mistral-saba-2506",
]

# (model_id, provider_name) pairs joined for convenience elsewhere.
ALL_MODELS: list[tuple[str, str]] = (
    [(m, "openrouter") for m in OPENROUTER_FREE_MODELS]
    + [(m, "groq") for m in GROQ_MODELS]
    + [(m, "mistral") for m in MISTRAL_MODELS]
)

# Hand-tuned parallel-matrix split: both groups have ~half OpenRouter +
# ~half Groq so neither serializes on the other.
GROUP1_MODELS: list[tuple[str, str]] = [
    # 13 OpenRouter + 4 Groq + 8 Mistral = 25
    ("openrouter/free",                                          "openrouter"),
    ("openrouter/owl-alpha",                                     "openrouter"),
    ("openai/gpt-oss-120b:free",                                 "openrouter"),
    ("openai/gpt-oss-20b:free",                                  "openrouter"),
    ("nvidia/nemotron-3-ultra-550b-a55b:free",                   "openrouter"),
    ("nvidia/nemotron-3-super-120b-a12b:free",                   "openrouter"),
    ("nvidia/nemotron-3-nano-30b-a3b:free",                      "openrouter"),
    ("nvidia/nemotron-nano-12b-v2-vl:free",                      "openrouter"),
    ("nvidia/nemotron-nano-9b-v2:free",                          "openrouter"),
    ("nvidia/nemotron-3.5-content-safety:free",                  "openrouter"),
    ("meta-llama/llama-3.3-70b-instruct:free",                   "openrouter"),
    ("google/gemma-4-26b-a4b-it:free",                           "openrouter"),
    ("liquid/lfm-2.5-1.2b-instruct:free",                        "openrouter"),
    ("llama-3.1-8b-instant",                                     "groq"),
    ("qwen/qwen3-32b",                                           "groq"),
    ("openai/gpt-oss-120b",                                      "groq"),
    ("groq/compound-mini",                                       "groq"),
    ("mistral-large-latest",                                     "mistral"),
    ("mistral-medium-latest",                                    "mistral"),
    ("mistral-small-latest",                                     "mistral"),
    ("ministral-8b-latest",                                      "mistral"),
    ("magistral-medium-latest",                                  "mistral"),
    ("codestral-latest",                                         "mistral"),
    ("devstral-latest",                                          "mistral"),
    ("open-mixtral-8x22b",                                       "mistral"),
]

GROUP2_MODELS: list[tuple[str, str]] = [
    # 10 OpenRouter + 6 Groq + 8 Mistral = 24
    ("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",       "openrouter"),
    ("meta-llama/llama-3.2-3b-instruct:free",                    "openrouter"),
    ("qwen/qwen3-coder:free",                                    "openrouter"),
    ("qwen/qwen3-next-80b-a3b-instruct:free",                    "openrouter"),
    ("nousresearch/hermes-3-llama-3.1-405b:free",                "openrouter"),
    ("poolside/laguna-m.1:free",                                 "openrouter"),
    ("poolside/laguna-xs.2:free",                                "openrouter"),
    ("cohere/north-mini-code:free",                              "openrouter"),
    ("liquid/lfm-2.5-1.2b-thinking:free",                        "openrouter"),
    ("cognitivecomputations/dolphin-mistral-24b-venice-edition:free", "openrouter"),
    ("meta-llama/llama-4-scout-17b-16e-instruct",                "groq"),
    ("qwen/qwen3.6-27b",                                         "groq"),
    ("openai/gpt-oss-20b",                                       "groq"),
    ("openai/gpt-oss-safeguard-20b",                             "groq"),
    ("groq/compound",                                            "groq"),
    ("allam-2-7b",                                               "groq"),
    ("mistral-tiny-latest",                                      "mistral"),
    ("ministral-3b-latest",                                      "mistral"),
    ("magistral-small-latest",                                   "mistral"),
    ("devstral-small-latest",                                    "mistral"),
    ("open-mistral-7b",                                          "mistral"),
    ("open-mixtral-8x7b",                                        "mistral"),
    ("mistral-saba-latest",                                      "mistral"),
    ("mistral-saba-2506",                                        "mistral"),
]


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
def call_model(
    model: str,
    provider_name: str,
    prompt: str,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Hit a model once, retrying with exponential backoff on HTTP 429/5xx."""
    provider = PROVIDERS[provider_name]
    api_key = os.getenv(provider["key_env"], "")
    if not api_key:
        return failure_result(model, provider_name, f"{provider['key_env']} not set")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": MODEL_MAX_TOKENS_OVERRIDES.get(model, DEFAULT_MAX_TOKENS),
        "stream": False,
    }
    body = json.dumps(payload).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "LLMstats/1.0 (+https://github.com/Saif658/LLMstats)",
    }
    headers.update(provider.get("extra_headers", {}))

    retryable_statuses = {429, 500, 502, 503, 504}
    last_result: dict[str, Any] | None = None

    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait = 2 ** attempt  # 2s, 4s, 8s ...
            print(f"  [retry {attempt}/{max_retries}] waiting {wait}s ...")
            time.sleep(wait)

        result = _call_model_once(model, provider_name, body, headers)
        last_result = result

        # Only retry on rate limit / transient upstream errors
        if result.get("success"):
            return result
        err = result.get("error") or ""
        is_retryable = False
        for code in retryable_statuses:
            if f"HTTP {code}" in err or err.startswith(f"HTTP {code}"):
                is_retryable = True
                break
        # Empty responses can race — retry once
        if err == "Empty response from API" and attempt < max_retries:
            is_retryable = True
        if not is_retryable or attempt >= max_retries:
            return result

    return last_result or failure_result(model, provider_name, "Unknown error")


def _call_model_once(
    model: str,
    provider_name: str,
    body: bytes,
    headers: dict[str, str],
) -> dict[str, Any]:
    provider = PROVIDERS[provider_name]
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
    print(f"History updated: {str(SCRIPT_DIR / 'history.db')}")


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
        # Mistral's free Experiment tier shares a ~1B-token/month cap across
        # the whole catalog. Wait longer than the global default until we've
        # confirmed we're not 429-cascading.
        delay = 2.0 if provider == "mistral" else 0.5
        time.sleep(delay)

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
