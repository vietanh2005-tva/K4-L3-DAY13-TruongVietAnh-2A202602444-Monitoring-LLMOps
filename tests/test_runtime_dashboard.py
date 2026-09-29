from __future__ import annotations

import json
from pathlib import Path

from app.dashboard import dashboard_metrics, render_dashboard


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_dashboard_computes_all_six_panel_metrics(tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    rows = [
        {"ts": "2026-09-29T07:00:00Z", "event": "request_received"},
        {
            "ts": "2026-09-29T07:00:01Z",
            "event": "response_sent",
            "latency_ms": 400,
            "ttft_ms": 50,
            "cost_usd": 0.002,
            "tokens_in": 100,
            "tokens_out": 80,
            "quality_score": 0.9,
            "tool_name": "retrieval",
            "tool_success": True,
        },
    ]
    _write(log_path, rows)

    metrics = dashboard_metrics(log_path)

    assert metrics["traffic_count"] == 1
    assert metrics["latency_p95"] == 400
    assert metrics["ttft_p95"] == 50
    assert metrics["retrieval_success"] == 100
    assert metrics["cost_total"] == 0.002
    assert metrics["tokens_in"] == 100
    assert metrics["tokens_out"] == 80
    assert metrics["quality_avg"] == 0.9


def test_dashboard_html_contains_contract_and_thresholds(tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    _write(log_path, [])

    page = render_dashboard(log_path)

    for title in (
        "Latency percentiles and TTFT",
        "Request traffic",
        "Error rate and retrieval success",
        "Cost over time",
        "Input and output tokens",
        "Quality proxy",
    ):
        assert title in page
    assert "Past 60 minutes" in page
    assert "Refresh: 30 seconds" in page
    assert "SLO: 99.5%" in page
