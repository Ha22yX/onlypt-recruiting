import json
from datetime import datetime, timezone

import app as onlypt


def write_events(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")


def traffic_event(event_type, ip, path="/", minute=0):
    created_at = datetime(2026, 7, 15, 14, minute, tzinfo=timezone.utc).isoformat()
    return {
        "type": event_type,
        "created_at": created_at,
        "path": path,
        "domain": "onlypt.co",
        "endpoint": "contact" if path == "/contact" else "home",
        "method": "POST" if event_type == "form_submission" else "GET",
        "ip": ip,
        "visitor_id": f"visitor-{ip}",
        "user_agent": "Mozilla/5.0",
        "device": "Desktop",
        "referrer": "",
        "region": {"ip": ip, "country": "United States", "region": "New York", "city": "New York"},
    }


def test_conversion_rate_counts_unique_submitters_not_submission_count(tmp_path, monkeypatch):
    monkeypatch.setattr(onlypt, "TRAFFIC_LOG_FILE", tmp_path / "traffic_events.jsonl")
    write_events(
        onlypt.TRAFFIC_LOG_FILE,
        [
            traffic_event("page_view", "198.51.100.10", "/", 1),
            traffic_event("form_submission", "198.51.100.10", "/contact", 2),
            traffic_event("form_submission", "198.51.100.10", "/contact", 3),
            traffic_event("page_view", "198.51.100.11", "/", 4),
        ],
    )

    summary = onlypt.summarize_traffic(None, None)

    assert summary["totals"]["unique_visitors"] == 2
    assert summary["totals"]["form_submissions"] == 2
    assert summary["totals"]["unique_form_submitters"] == 1
    assert summary["totals"]["conversion_rate"] == 50.0
