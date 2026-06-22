"""Shared SQLite utilities for reading/writing benchmark history."""

import sqlite3
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORY_DB = REPO_ROOT / "history.db"
MAX_RUNS = 720


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS runs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT    NOT NULL,
            prompt        TEXT,
            success_count INTEGER,
            total_models  INTEGER,
            fastest_model TEXT,
            fastest_time  INTEGER
        );
        CREATE TABLE IF NOT EXISTS model_results (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id           INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            model            TEXT    NOT NULL,
            provider         TEXT,
            success          INTEGER NOT NULL DEFAULT 0,
            error            TEXT,
            response_time    INTEGER,
            tokens_generated INTEGER,
            total_tokens     INTEGER,
            response         TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_mr_run     ON model_results(run_id);
        CREATE INDEX IF NOT EXISTS idx_mr_model   ON model_results(model);
        CREATE INDEX IF NOT EXISTS idx_mr_provider ON model_results(provider);
        CREATE INDEX IF NOT EXISTS idx_runs_ts    ON runs(timestamp);
    """)


def write_run(run: dict[str, Any], db_path: Path = HISTORY_DB) -> None:
    """Insert a benchmark run into the database and prune runs beyond MAX_RUNS."""
    summary = run.get("summary", {})
    conn = sqlite3.connect(str(db_path))
    try:
        init_schema(conn)
        cur = conn.execute(
            """INSERT INTO runs (timestamp, prompt, success_count, total_models, fastest_model, fastest_time)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                run.get("timestamp"),
                run.get("prompt"),
                summary.get("successCount"),
                summary.get("totalModels"),
                summary.get("fastestModel"),
                summary.get("fastestTime"),
            ),
        )
        run_id = cur.lastrowid
        conn.executemany(
            """INSERT INTO model_results
               (run_id, model, provider, success, error, response_time, tokens_generated, total_tokens, response)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    run_id,
                    m.get("model"),
                    m.get("provider"),
                    1 if m.get("success") else 0,
                    m.get("error"),
                    m.get("responseTime"),
                    m.get("tokensGenerated"),
                    m.get("totalTokens"),
                    m.get("response"),
                )
                for m in run.get("models", [])
            ],
        )
        conn.execute(
            f"DELETE FROM runs WHERE id NOT IN "
            f"(SELECT id FROM runs ORDER BY timestamp DESC LIMIT {MAX_RUNS})"
        )
        conn.commit()
    finally:
        conn.close()
