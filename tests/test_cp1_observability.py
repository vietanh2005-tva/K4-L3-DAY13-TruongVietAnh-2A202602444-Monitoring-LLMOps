from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

from app import logging_config
from app.main import app


def _post_chat(headers: dict[str, str] | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/chat",
                headers=headers,
                json={
                    "user_id": "student@example.com",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Call 090 123 4567 about CCCD 012345678901",
                },
            )

    return asyncio.run(send())


def test_generated_correlation_id_headers_and_scrubbed_log(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    response = _post_chat()

    assert response.status_code == 200
    correlation_id = response.headers["x-request-id"]
    assert re.fullmatch(r"req-[0-9a-f]{8}", correlation_id)
    assert response.headers["x-response-time-ms"].isdigit()

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    request_event = next(record for record in records if record["event"] == "request_received")
    assert request_event["correlation_id"] == correlation_id
    assert request_event["session_id"] == "session-01"
    assert request_event["feature"] == "qa"
    assert request_event["model"] == "claude-sonnet-4-5"
    assert request_event["env"] == "dev"
    assert request_event["user_id_hash"] != "student@example.com"

    raw_log = log_path.read_text(encoding="utf-8")
    assert "student@example.com" not in raw_log
    assert "090 123 4567" not in raw_log
    assert "012345678901" not in raw_log


def test_incoming_request_id_is_propagated(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")
    response = _post_chat({"x-request-id": "req-deadbeef"})
    assert response.headers["x-request-id"] == "req-deadbeef"
