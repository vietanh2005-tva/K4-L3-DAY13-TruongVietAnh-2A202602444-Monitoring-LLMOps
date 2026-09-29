from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_slo_and_alert_contracts_are_complete() -> None:
    slo = yaml.safe_load((REPO_ROOT / "config" / "slo.yaml").read_text(encoding="utf-8"))
    primary = slo["primary_slo"]
    assert primary["target_percent"] == 99.5
    assert primary["error_budget_percent"] == 100 - primary["target_percent"]

    alert_config = yaml.safe_load(
        (REPO_ROOT / "config" / "alert_rules.yaml").read_text(encoding="utf-8")
    )
    alerts = alert_config["alerts"]
    assert len(alerts) == 3

    required = {
        "name",
        "severity",
        "condition",
        "duration",
        "type",
        "channel",
        "slack_channel",
        "owner",
        "runbook",
    }
    for alert in alerts:
        assert required.issubset(alert)
        assert alert["type"] == "symptom-based"
        assert alert["channel"] == "slack"
        assert alert["slack_channel"].startswith("#")
        assert "TODO" not in str(alert)
