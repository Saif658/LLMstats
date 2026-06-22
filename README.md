<div align="center">

# LLMstats

**Real-time benchmarking of free-tier models from OpenRouter and Groq — automated every 2 hours, zero infrastructure.**

[![Live Dashboard](https://img.shields.io/badge/🌐%20live-github.io-06b6d4?style=flat-square)](https://saif658.github.io/LLMstats/)
[![Benchmark](https://img.shields.io/github/actions/workflow/status/Saif658/LLMstats/benchmark.yml?label=benchmarks&style=flat-square)](.github/workflows/benchmark.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)](LICENSE)

> Forked from the architecture of [NIMStats](https://github.com/MauroDruwel/NIMStats), rebuilt to compare two OpenAI-compatible providers side-by-side.

</div>

---

## ✨ What is LLMstats?

**LLMstats** automatically benchmarks **13 free-tier models** every 2 hours — 6 served by [OpenRouter](https://openrouter.ai/) (the unified router, free-tier) and 7 served by [Groq](https://groq.com/) (the LPU cloud) — and publishes the results to a live, interactive dashboard. No servers, no subscriptions — just fork the repo, drop in two API keys, and go.

| 🏎️ Every 2h | 📊 Interactive Charts | 🔁 Zero Infra | 🔀 Multi-Provider |
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

The dashboard auto-refreshes every 2 hours after that. ✨

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
<summary><b>13 models across 2 providers</b</summary>

### 🟣 OpenRouter (free-tier)
| Model | Note |
|-------|------|
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 550B MoE flagship |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | Compact reasoning |
| `nvidia/nemotron-3.5-content-safety:free` | Content-safety fine-tune |
| `poolside/laguna-m.1:free` | Code-specialized |
| `poolside/laguna-xs.2:free` | Code-specialized (smaller) |
| `cohere/north-mini-code:free` | Code-specialized |

### 🟠 Groq
| Model | Note |
|-------|------|
| `llama-3.3-70b-versatile` | Versatile default |
| `llama-3.1-8b-instant` | Ultra-low latency |
| `meta-llama/llama-4-maverick-17b-128e-instruct` | Llama 4 MoE flagship |
| `meta-llama/llama-4-scout-17b-16e-instruct` | Llama 4 Scout |
| `mistral-saba-24b` | Mistral reasoning |
| `gemma2-9b-it` | Gemma 2 9B |
| `meta-llama/llama-3.1-70b-versatile` | Older 70B baseline |

</details>

---

## 🏗️ How it works

```
┌─── GitHub Actions (every 2h) ────────────────────────────────────────────┐
│                                                                          │
│   ┌─────────────────────┐         ┌─────────────────────┐                │
│   │  Job 1 — Group A    │         │  Job 2 — Group B    │  in parallel    │
│   │  7 models (mixed)   │         │  7 models (mixed)   │                │
│   └──────────┬──────────┘         └──────────┬──────────┘                │
│              └──────────────┬───────────────┘                           │
│                     ┌────────▼────────┐                                 │
│                     │  Merge + commit │  → history.db updated in repo   │
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

Edit `PROMPT` in `scripts/test_models.py`:
```python
PROMPT = "Your custom prompt here"
```

</details>

<details>
<summary><b>Add or remove models</b</summary>

Edit `OPENROUTER_FREE_MODELS` and `GROQ_MODELS` in `scripts/test_models.py`. The two lists get split roughly in half between `group1` and `group2` jobs.

</details>

<details>
<summary><b>Change the schedule</b</summary>

Edit `.github/workflows/benchmark.yml`:
```yaml
- cron: '0 */2 * * *'   # every 2 hours (default)
- cron: '0 */1 * * *'   # every hour
- cron: '0 0 */6 * *'   # every 6 hours
```

</details>

<details>
<summary><b>Run locally</b</summary>

```bash
# Serve the dashboard (requires history.db — created after first workflow run)
python3 -m http.server 8000
# Open http://localhost:8000

# Run benchmarks manually (requires API keys as env vars)
export OPENROUTER_API_KEY=...
export GROQ_API_KEY=...
python3 scripts/test_models.py            # all models
MODEL_GROUP=group1 python3 scripts/test_models.py   # one half
```

</details>

---

## 📦 Data storage

`history.db` is a SQLite database persisted in the repo. The browser loads it via [sql.js](https://sql.js.org/) (WebAssembly) and queries it entirely client-side. `scripts/results*.json` are temporary per-job artifacts that never get committed ([.gitignored](.gitignore)).

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
