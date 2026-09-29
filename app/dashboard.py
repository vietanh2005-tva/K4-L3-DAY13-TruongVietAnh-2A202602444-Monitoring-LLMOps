from __future__ import annotations

import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"


def _read_rows(path: Path = LOG_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, round((percentile / 100) * len(ordered) + 0.5) - 1))
    return float(ordered[rank])


def dashboard_metrics(
    path: Path = LOG_PATH,
    *,
    now: datetime | None = None,
    window_minutes: int = 60,
) -> dict[str, float | int]:
    rows = _read_rows(path)
    parsed = [(row, _parse_ts(row.get("ts"))) for row in rows]
    observed_times = [ts for _, ts in parsed if ts is not None]
    reference = now or (max(observed_times) if observed_times else datetime.now(timezone.utc))
    cutoff = reference - timedelta(minutes=window_minutes)
    window = [row for row, ts in parsed if ts is not None and cutoff <= ts <= reference]

    received = [row for row in window if row.get("event") == "request_received"]
    responses = [row for row in window if row.get("event") == "response_sent"]
    failures = [row for row in window if row.get("event") == "request_failed"]
    latencies = [float(row["latency_ms"]) for row in responses if isinstance(row.get("latency_ms"), (int, float))]
    ttfts = [float(row["ttft_ms"]) for row in responses if isinstance(row.get("ttft_ms"), (int, float))]
    retrieval_events = [row for row in window if row.get("tool_name") == "retrieval" and row.get("tool_success") is not None]
    retrieval_successes = sum(row.get("tool_success") is True for row in retrieval_events)
    costs = [float(row.get("cost_usd", 0.0) or 0.0) for row in responses]
    quality = [float(row["quality_score"]) for row in responses if isinstance(row.get("quality_score"), (int, float))]

    return {
        "latency_p50": _percentile(latencies, 50),
        "latency_p95": _percentile(latencies, 95),
        "latency_p99": _percentile(latencies, 99),
        "ttft_p95": _percentile(ttfts, 95),
        "traffic_count": len(received),
        "traffic_rate": round(len(received) / max(window_minutes, 1), 2),
        "error_rate": round((len(failures) / len(received) * 100) if received else 0.0, 2),
        "retrieval_success": round((retrieval_successes / len(retrieval_events) * 100) if retrieval_events else 0.0, 2),
        "cost_total": round(sum(costs), 6),
        "tokens_in": sum(int(row.get("tokens_in", 0) or 0) for row in responses),
        "tokens_out": sum(int(row.get("tokens_out", 0) or 0) for row in responses),
        "quality_avg": round(mean(quality), 3) if quality else 0.0,
    }


def render_dashboard(path: Path = LOG_PATH) -> str:
    m = dashboard_metrics(path)
    panels = [
        ("Latency percentiles and TTFT", f"P50 {m['latency_p50']:.0f} · P95 {m['latency_p95']:.0f} · P99 {m['latency_p99']:.0f} ms", f"TTFT P95 {m['ttft_p95']:.0f} ms", "SLO P95 ≤ 3000 ms", m["latency_p95"] <= 3000),
        ("Request traffic", f"{m['traffic_count']} requests", f"{m['traffic_rate']:.2f} requests/min", "Expected ≥ 1 request/min", m["traffic_rate"] >= 1),
        ("Error rate and retrieval success", f"Errors {m['error_rate']:.2f}%", f"Retrieval success {m['retrieval_success']:.2f}%", "Error rate ≤ 2%", m["error_rate"] <= 2),
        ("Cost over time", f"${m['cost_total']:.6f} total", "60-minute window", "Budget ≤ $2.50", m["cost_total"] <= 2.5),
        ("Input and output tokens", f"Input {m['tokens_in']:,}", f"Output {m['tokens_out']:,}", "Total ≤ 50,000 tokens", m["tokens_in"] + m["tokens_out"] <= 50000),
        ("Quality proxy", f"{m['quality_avg']:.3f} / 1.000", "Mean heuristic score", "Quality ≥ 0.75", m["quality_avg"] >= 0.75),
    ]
    cards = "".join(
        f"""
        <article class="card {'ok' if ok else 'alert'}">
          <div class="status">{'WITHIN THRESHOLD' if ok else 'THRESHOLD BREACH'}</div>
          <h2>{html.escape(title)}</h2>
          <div class="value">{html.escape(primary)}</div>
          <div class="secondary">{html.escape(secondary)}</div>
          <div class="threshold">{html.escape(threshold)}</div>
        </article>
        """
        for title, primary, secondary, threshold, ok in panels
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="30">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>K4-L3A Day 13 Monitoring Dashboard</title>
<style>
:root{{--bg:#08111f;--panel:#111f33;--line:#263a55;--text:#e8f0fb;--muted:#91a4bd;--ok:#31d0aa;--bad:#ff6b7a;--accent:#70a5ff}}
*{{box-sizing:border-box}} body{{margin:0;background:linear-gradient(145deg,#07101c,#0d1a2a);color:var(--text);font-family:Inter,Segoe UI,sans-serif}}
main{{max-width:1400px;margin:auto;padding:30px}} header{{display:flex;justify-content:space-between;gap:20px;align-items:end;margin-bottom:24px}}
h1{{margin:0;font-size:30px}} .meta{{color:var(--muted);text-align:right;line-height:1.6}} .grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}}
.card{{background:var(--panel);border:1px solid var(--line);border-top:4px solid var(--ok);border-radius:14px;padding:20px;min-height:210px;box-shadow:0 14px 35px #0005}}
.card.alert{{border-top-color:var(--bad)}} .status{{font-size:11px;letter-spacing:.12em;color:var(--ok);font-weight:700}} .alert .status{{color:var(--bad)}}
h2{{font-size:17px;margin:16px 0 22px;color:#cfe0f8}} .value{{font-size:25px;font-weight:750;line-height:1.25}} .secondary{{font-size:16px;color:var(--muted);margin-top:10px}}
.threshold{{margin-top:24px;border-top:1px solid var(--line);padding-top:14px;color:var(--accent);font-size:13px}} footer{{margin-top:20px;color:var(--muted);font-size:13px}}
@media(max-width:900px){{.grid{{grid-template-columns:1fr 1fr}}}} @media(max-width:620px){{.grid{{grid-template-columns:1fr}}header{{display:block}}.meta{{text-align:left;margin-top:10px}}}}
</style></head><body><main>
<header><div><h1>K4-L3A Day 13 · Monitoring &amp; LLMOps</h1><p>Runtime dashboard backed by <code>data/logs.jsonl</code></p></div>
<div class="meta">Time range: Past 60 minutes<br>Refresh: 30 seconds<br>SLO: 99.5% successful requests ≤ 3000 ms</div></header>
<section class="grid">{cards}</section>
<footer>Source: structured JSON logs · Incident workflow: Metrics → Logs → Traces → Root cause</footer>
</main></body></html>"""
