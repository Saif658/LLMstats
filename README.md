<div align="center">

# LLMstats

**Real-time benchmarking of free-tier models from OpenRouter and Groq — automated roughly every 3 hours, zero infrastructure.**

[![Live Dashboard](https://img.shields.io/badge/🌐%20live-github.io-06b6d4?style=flat-square)](https://saif658.github.io/LLMstats/)
[![Benchmark](https://img.shields.io/github/actions/workflow/status/Saif658/LLMstats/benchmark.yml?label=benchmarks&style=flat-square)](.github/workflows/benchmark.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)](LICENSE)

**🌐 [saif658.github.io/LLMstats](https://saif658.github.io/LLMstats/)** — live, public, refreshes roughly every 3 hours

> Forked from the architecture of [NIMStats](https://github.com/MauroDruwel/NIMStats), rebuilt to compare two OpenAI-compatible providers side-by-side.

</div>

---

## ✨ What is LLMstats?

**LLMstats** automatically benchmarks **37 free-tier models** roughly every 3 hours — **26 served by [OpenRouter](https://openrouter.ai/) (the unified router, 12 upstream providers) and 11 served by [Groq](https://groq.com/) (the LPU cloud)** — and publishes the results to a live, interactive dashboard. No servers, no subscriptions — just fork the repo, drop in two API keys, and go.

| 🏎️ Every ~3h | 📊 Interactive Charts | 🔁 Zero Infra | 🔀 Multi-Provider |
|:---:|:---:|:---:|:---:|
| GitHub Actions cron | Speed, throughput, reliability | Static site + free CI/CD | OpenRouter ↔ Groq comparisons |

---

## ⚡ Quick Start

> A working dashboard in under 5 minutes.

### 1. Fork & clone

```bash
git clone https://github.com/Saif658/LLMstats.git
cd LLMstats
```

### 2. Get free API keys

| Provider | Where to get it |
|----------|-----------------|
| OpenRouter  | [openrouter.ai/keys](https://openrouter.ai/keys) — sign up, generate a key |
| Groq        | [console.groq.com/keys](https://console.groq.com/keys) — sign up, generate a key |

### 3. Add secrets

In your forked repo: **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|------|-------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key |
| `GROQ_API_KEY`       | Your Groq API key |

### 4. Enable GitHub Pages

**Settings → Pages → Build from "GitHub Actions"**.

### 5. Run your first benchmark

**Actions → Benchmark OpenRouter + Groq Models → Run workflow**.

The dashboard auto-refreshes roughly every 3 hours after that. ✨

---

## 📊 Dashboard

| Tab        | What you get |
|------------|--------------|
| 📊 **Overview**      | 5 KPI cards · success-rate trend · top-10 speed & throughput bars · per-model reliability pills |
| 🏆 **Leaderboard**   | Composite score · sortable columns · trend indicators · **provider chips** (OpenRouter vs Groq) |
| 🔬 **Explorer**      | Per-model deep dive · response time history · error breakdown · availability heatmap |
| ⏱ **Timeline**       | Filterable run history · expandable run cards with full per-model detail |
| ⚔️ **Compare**       | Head-to-head overlay · win-rate stats · side-by-side metric comparison |

---

## 🤖 Benchmarked models (free tier)

<details>
<summary><b>33 models across 2 gateways, 11+ upstream providers</b</summary>

### 🟣 OpenRouter · 23 models · 11 upstream providers
| Upstream | Model | Note |
|----------|-------|------|
| **OpenRouter** | `openrouter/free` | OR's own free flagship |
| **OpenRouter** | `openrouter/owl-alpha` | OR preview alpha |
| **OpenAI**     | `openai/gpt-oss-120b:free` | Open-source 120B |
| **OpenAI**     | `openai/gpt-oss-20b:free`  | Open-source 20B |
| **Meta**       | `meta-llama/llama-3.3-70b-instruct:free` | Large general-purpose |
| **Meta**       | `meta-llama/llama-3.2-3b-instruct:free`  | Lightweight Llama |
| **NVIDIA**     | `nvidia/nemotron-3-ultra-550b-a55b:free`               | 550B MoE flagship |
| **NVIDIA**     | `nvidia/nemotron-3-super-120b-a12b:free`                | 120B MoE super |
| **NVIDIA**     | `nvidia/nemotron-3-nano-30b-a3b:free`                   | Compact MoE |
| **NVIDIA**     | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`    | Compact reasoning |
| **NVIDIA**     | `nvidia/nemotron-nano-12b-v2-vl:free`                   | Vision-language |
| **NVIDIA**     | `nvidia/nemotron-nano-9b-v2:free`                       | Compact 9B |
| **NVIDIA**     | `nvidia/nemotron-3.5-content-safety:free`               | Content safety guard |
| **Qwen**       | `qwen/qwen3-coder:free`                | Qwen 3 coding |
| **Qwen**       | `qwen/qwen3-next-80b-a3b-instruct:free` | Qwen 3 80B MoE |
| **Google**     | `google/gemma-4-26b-a4b-it:free`        | Gemma 4 mid-size |
| **Google**     | `google/lyria-3-pro-preview`            | Lyria 3 pro (preview) |
| **Google**     | `google/lyria-3-clip-preview`           | Lyria 3 clip (preview) |
| **Nous**       | `nousresearch/hermes-3-llama-3.1-405b:free` | Hermes 3 405B |
| **Nex AGI**    | `nex-agi/nex-n2-pro:free`               | Nex N2 Pro |
| **Poolside**   | `poolside/laguna-m.1:free`              | Laguna m.1 |
| **Poolside**   | `poolside/laguna-xs.2:free`             | Laguna xs.2 |
| **Cohere**     | `cohere/north-mini-code:free`           | Cohere North mini-code |
| **Liquid**     | `liquid/lfm-2.5-1.2b-instruct:free`     | Liquid LFM 2.5 1.2B |
| **Liquid**     | `liquid/lfm-2.5-1.2b-thinking:free`     | Liquid LFM 2.5 1.2B thinking |
| **Cognitive Computations** | `cognitivecomputations/dolphin-mistral-24b-venice-edition:free` | Dolphin Mistral 24B Venice |

### 🟠 Groq · 10 chat models
| Model | Note |
|-------|------|
| `llama-3.1-8b-instant`                     | Ultra-low latency |
| `meta-llama/llama-4-scout-17b-16e-instruct` | Llama 4 Scout MoE |
| `qwen/qwen3-32b`                           | Qwen 3 flagship |
| `qwen/qwen3.6-27b`                         | Qwen 3.6 mid-size |
| `openai/gpt-oss-120b`                      | Open-source 120B |
| `openai/gpt-oss-20b`                       | Open-source 20B |
| `openai/gpt-oss-safeguard-20b`             | Safety-guard 20B |
| `groq/compound`                            | Groq compound agentic |
| `groq/compound-mini`                       | Groq compound-mini agentic |
| `allam-2-7b`                               | Allam (small MoE) |

</details>

---

## 🏗️ How it works

```
┌─── GitHub Actions (every ~3h) ────────────────────────────────────────────┐
│                                                                          │
│   ┌─────────────────────┐         ┌─────────────────────┐                │
│   │  Job 1 — Group A    │         │  Job 2 — Group B    │  in parallel    │
│   │  8 models (mixed)   │         │  9 models (mixed)   │                │
│   └──────────┬──────────┘         └──────────┬──────────┘                │
│              └──────────────┬───────────────┘                           │
│                     ┌────────▼────────┐                                 │
│                     │  Merge + commit │  → benchmark/history.db + docs/history.db │
│                     └─────────────────┘                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                          ┌───────────▼──────────┐
                          │  Static Dashboard    │  GitHub Pages
                          │  (sql.js client)     │
                          └──────────────────────┘
```

**Parallel matrix ≈ 50% faster ⚡**

---

## 🛠️ Customization

<details>
<summary><b>Change the prompt</b</summary>

Edit `PROMPT` in `benchmark/test_models.py`:
```python
PROMPT = "Your custom prompt here"
```

</details>

<details>
<summary><b>Add or remove models</b</summary>

Edit `OPENROUTER_FREE_MODELS` and `GROQ_MODELS` in `benchmark/test_models.py`. The two lists get split roughly in half between `group1` and `group2` jobs.

</details>

<details>
<summary><b>Change the schedule</b</summary>

Edit `.github/workflows/benchmark.yml`:
```yaml
- cron: '0 */3 * * *'   # every 3 hours (default)
- cron: '0 */1 * * *'   # every hour
- cron: '0 0 */6 * *'   # every 6 hours
```

</details>

<details>
<summary><b>Run locally</b</summary>

```bash
# Serve the dashboard from the repo root (serves docs/index.html + docs/history.db)
python3 -m http.server 8000
# Open http://localhost:8000/docs/

# Run benchmarks manually (requires API keys as env vars)
export OPENROUTER_API_KEY=...
export GROQ_API_KEY=...
python3 benchmark/test_models.py            # all models
MODEL_GROUP=group1 python3 benchmark/test_models.py   # one half
```

</details>

---

## 📦 Data storage

`benchmark/history.db` is a SQLite database persisted in the repo. The browser loads it via [sql.js](https://sql.js.org/) (WebAssembly) and queries it entirely client-side. `benchmark/results*.json` are temporary per-job artifacts that never get committed ([.gitignored](.gitignore)). On every merge the workflow mirrors the latest `benchmark/history.db` to `docs/history.db` next to the dashboard.

**Schema:**

```sql
runs          (id, timestamp, prompt, success_count, total_models, fastest_model, fastest_time)
model_results (run_id, model, provider, success, error, response_time, tokens_generated, total_tokens, response)
```

Results are pruned to the most recent **720 runs** to keep `history.db` from growing unbounded.

**Benchmark parameters:** `temperature: 0.7` · `top_p: 0.9` · `max_tokens: 500` · OpenAI-compatible chat completions API.

---

## 🤝 Contributing

PRs and ideas welcome:

- 🆕 Add new free-tier models from each provider
- 📊 New chart types or dashboard widgets
- 🐛 Bug fixes and perf improvements
- 📖 Docs / translations

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

Inspired by [NIMStats](https://github.com/MauroDruwel/NIMStats) · ⚡ Powered by GitHub Actions

</div>
