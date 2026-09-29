from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from dotenv import load_dotenv
from langfuse import get_client


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.dashboard import dashboard_metrics, render_dashboard


EVIDENCE_DIR = REPO_ROOT / "submission" / "evidence"
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
INCIDENT_CORRELATION_ID = "req-8de5e3d9"
INCIDENT_TRACE_ID = "dbdfdd1ad30040ef591665fc0ba4884b"
CHALLENGE_IDS = {
    "req-cce1e7c1",
    "req-1f18d223",
    "req-8de5e3d9",
    "req-596865be",
    "req-6313c301",
}


def _fmt(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return "-"
    return str(value)


def _write(name: str, content: str) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / name).write_text(content.rstrip() + "\n", encoding="utf-8")


def _log_rows() -> list[dict]:
    return [
        json.loads(line)
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _dashboard_svg(metrics: dict[str, float | int]) -> str:
    cards = [
        ("Latency P50 / P95 / P99", f"{metrics['latency_p50']:.0f} / {metrics['latency_p95']:.0f} / {metrics['latency_p99']:.0f} ms", "SLO P95 <= 3000 ms"),
        ("Traffic", f"{metrics['traffic_count']} requests | {metrics['traffic_rate']:.2f}/min", "Past 60 minutes"),
        ("Errors / retrieval", f"{metrics['error_rate']:.2f}% / {metrics['retrieval_success']:.2f}%", "Error <= 2%"),
        ("Cost", f"${metrics['cost_total']:.6f}", "Budget <= $2.50"),
        ("Tokens in / out", f"{metrics['tokens_in']:,} / {metrics['tokens_out']:,}", "Total <= 50,000"),
        ("Quality proxy", f"{metrics['quality_avg']:.3f}", "Target >= 0.75"),
    ]
    blocks: list[str] = []
    for index, (title, value, threshold) in enumerate(cards):
        col, row = index % 3, index // 3
        x, y = 40 + col * 420, 155 + row * 245
        breached = title.startswith("Latency") and float(metrics["latency_p95"]) > 3000
        color = "#ff6b7a" if breached else "#31d0aa"
        blocks.append(
            f'<rect x="{x}" y="{y}" width="380" height="205" rx="16" fill="#111f33" stroke="#263a55"/>'
            f'<rect x="{x}" y="{y}" width="380" height="5" rx="2" fill="{color}"/>'
            f'<text x="{x+24}" y="{y+42}" fill="#cfe0f8" font-size="19">{escape(title)}</text>'
            f'<text x="{x+24}" y="{y+102}" fill="#ffffff" font-size="29" font-weight="700">{escape(value)}</text>'
            f'<text x="{x+24}" y="{y+160}" fill="#70a5ff" font-size="15">{escape(threshold)}</text>'
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1340" height="700" viewBox="0 0 1340 700">
<rect width="1340" height="700" fill="#08111f"/>
<text x="40" y="58" fill="#ffffff" font-family="Segoe UI, sans-serif" font-size="30" font-weight="700">K4-L3A Day 13 Monitoring &amp; LLMOps</text>
<text x="40" y="94" fill="#91a4bd" font-family="Segoe UI, sans-serif" font-size="16">Runtime source: data/logs.jsonl · Past 60 minutes · Refresh 30 seconds</text>
<g font-family="Segoe UI, sans-serif">{''.join(blocks)}</g>
<text x="40" y="660" fill="#91a4bd" font-family="Segoe UI, sans-serif" font-size="15">Metrics → Logs → Traces → Root cause</text>
</svg>'''


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        raise SystemExit("Langfuse keys are required in .env")

    client = get_client()
    field_groups = "basic,time,metadata,model,usage,prompt,metrics,trace_context"
    roots = client.api.observations.get_many(
        is_root_observation=True,
        limit=50,
        fields=field_groups,
        expand_metadata=(
            "correlation_id,feature,model,prompt_name,prompt_label,"
            "prompt_version,prompt_source,query_preview,doc_count"
        ),
    ).model_dump()["data"]
    roots.sort(key=lambda row: _fmt(row.get("start_time")), reverse=True)
    trace_lines = [f"Langfuse root traces: {len(roots)}", ""]
    trace_by_correlation: dict[str, dict] = {}
    for row in roots:
        metadata = row.get("metadata") or {}
        correlation_id = metadata.get("correlation_id", "-")
        trace_by_correlation[str(correlation_id)] = row
        trace_lines.append(
            " | ".join(
                [
                    f"trace_id={row.get('trace_id')}",
                    f"start={_fmt(row.get('start_time'))}",
                    f"latency_s={row.get('latency')}",
                    f"correlation_id={correlation_id}",
                    f"prompt={metadata.get('prompt_name', '-')}",
                    f"label={metadata.get('prompt_label', '-')}",
                    f"version={metadata.get('prompt_version', '-')}",
                ]
            )
        )
    _write("06-trace-list.txt", "\n".join(trace_lines))

    observations = client.api.observations.get_many(
        trace_id=INCIDENT_TRACE_ID,
        limit=20,
        fields=field_groups,
        expand_metadata="correlation_id,prompt_name,prompt_label,prompt_version,prompt_source",
    ).model_dump()["data"]
    observations.sort(key=lambda row: _fmt(row.get("start_time")))
    waterfall_lines = [
        f"trace_id={INCIDENT_TRACE_ID}",
        f"correlation_id={INCIDENT_CORRELATION_ID}",
        "",
    ]
    for row in observations:
        waterfall_lines.append(
            " | ".join(
                [
                    f"name={row.get('name')}",
                    f"type={row.get('type')}",
                    f"latency_s={row.get('latency')}",
                    f"parent={row.get('parent_observation_id') or 'ROOT'}",
                    f"model={row.get('model') or '-'}",
                    f"usage={row.get('usage_details') or {}}",
                    f"cost={row.get('cost_details') or {}}",
                ]
            )
        )
    waterfall = "\n".join(waterfall_lines)
    _write("07-trace-waterfall.txt", waterfall)
    _write("14-incident-trace.txt", waterfall)

    incident_root = trace_by_correlation[INCIDENT_CORRELATION_ID]
    metadata = incident_root.get("metadata") or {}
    safe_metadata = {
        key: metadata.get(key)
        for key in (
            "correlation_id",
            "feature",
            "model",
            "prompt_name",
            "prompt_label",
            "prompt_version",
            "prompt_source",
            "query_preview",
            "doc_count",
        )
    }
    _write(
        "08-trace-metadata.txt",
        f"trace_id={INCIDENT_TRACE_ID}\n" + json.dumps(safe_metadata, ensure_ascii=False, indent=2),
    )

    prompt_v1 = client.get_prompt("day13-chat", version=1)
    prompt_v2 = client.get_prompt("day13-chat", version=2)
    production = client.get_prompt("day13-chat", label="production")
    _write(
        "09-prompt-versions.txt",
        "\n".join(
            [
                f"name=day13-chat",
                f"v1 labels={prompt_v1.labels} template={prompt_v1.prompt!r}",
                f"v2 labels={prompt_v2.labels} template={prompt_v2.prompt!r}",
                f"baseline_trace_id={trace_by_correlation['req-b1000001']['trace_id']}",
                f"candidate_trace_id={trace_by_correlation['req-c2000002']['trace_id']}",
            ]
        ),
    )
    _write(
        "10-prompt-rollback.txt",
        "\n".join(
            [
                "Promote: production -> version 2",
                f"production_v2_trace_id={trace_by_correlation['req-d2000002']['trace_id']}",
                "Rollback: production -> version 1",
                f"current_production_version={production.version}",
                f"current_v1_labels={prompt_v1.labels}",
                f"current_v2_labels={prompt_v2.labels}",
            ]
        ),
    )

    metrics = dashboard_metrics(LOG_PATH)
    _write("11-dashboard-overview.html", render_dashboard(LOG_PATH))
    _write("11-dashboard-overview.svg", _dashboard_svg(metrics))
    _write(
        "12-incident-metric.txt",
        "\n".join(
            [
                "challenge_id=day13-k4-l3a-monitoring-llmops-v1",
                "window=2026-09-29T07:30:42Z..2026-09-29T07:30:56Z",
                f"latency_p95_ms={metrics['latency_p95']}",
                f"ttft_p95_ms={metrics['ttft_p95']}",
                "threshold_ms=3000",
                "symptom=tail latency threshold breach",
            ]
        ),
    )

    rows = _log_rows()
    incident_log = next(
        row
        for row in rows
        if row.get("event") == "response_sent" and row.get("correlation_id") == INCIDENT_CORRELATION_ID
    )
    safe_log = {
        key: incident_log.get(key)
        for key in (
            "ts",
            "event",
            "correlation_id",
            "feature",
            "model",
            "latency_ms",
            "ttft_ms",
            "tokens_in",
            "tokens_out",
            "cost_usd",
            "quality_score",
            "tool_name",
            "tool_success",
        )
    }
    _write("13-incident-log.txt", json.dumps(safe_log, ensure_ascii=False, indent=2))
    print(f"Exported runtime evidence to {EVIDENCE_DIR}")


if __name__ == "__main__":
    main()
