import csv
import json

import pytest

import app as onlypt


@pytest.fixture()
def client(tmp_path, monkeypatch):
    instance = tmp_path / "instance"
    monkeypatch.setattr(onlypt, "LEADS_FILE", instance / "leads.csv")
    monkeypatch.setattr(onlypt, "LEAD_THREADS_FILE", instance / "lead_threads.json")
    monkeypatch.setattr(onlypt, "SUBMISSION_LIMIT_FILE", instance / "submission_limits.json")
    monkeypatch.setattr(onlypt, "EMAIL_RATE_FILE", instance / "email_rate.json")
    monkeypatch.setattr(onlypt, "EMAIL_QUEUE_FILE", instance / "email_queue.json")
    monkeypatch.setattr(onlypt, "TRAFFIC_LOG_FILE", instance / "traffic_events.jsonl")
    monkeypatch.setattr(onlypt, "IP_REGION_CACHE_FILE", instance / "ip_region_cache.json")
    monkeypatch.setattr(onlypt, "CONTACT_IP_BLOCKS_FILE", instance / "contact_ip_blocks.json", raising=False)
    monkeypatch.setattr(onlypt, "notify_lead_email", lambda form_data: False)
    monkeypatch.setattr(onlypt, "notify_submitter_confirmation", lambda form_data: False)
    monkeypatch.setattr(onlypt, "notify_lead_whatsapp", lambda form_data: False)
    monkeypatch.setattr(
        onlypt,
        "lookup_ip_region",
        lambda ip_value: {"ip": ip_value, "country": "Testland", "region": "", "city": ""},
    )
    onlypt.app.config.update(TESTING=True, SECRET_KEY="test-secret")
    with onlypt.app.test_client() as test_client:
        with test_client.session_transaction() as session:
            session["admin_authenticated"] = True
        yield test_client


def post_contact(client, ip_value="203.0.113.9"):
    with client.session_transaction() as session:
        session["contact_form_token"] = "token-123"
        session["contact_form_started_at"] = 0
        session["contact_honeypot_name"] = "company_website"
    return client.post(
        "/contact",
        data={
            "contact_form_token": "token-123",
            "audience": "employer",
            "name": "Blocked Visitor",
            "email": "blocked@example.com",
            "organization": "Blocked Org",
            "phone": "5551234567",
            "role": "Clinic",
            "message": "Please contact me.",
        },
        headers={"X-Forwarded-For": ip_value},
    )


def read_lead_rows():
    if not onlypt.LEADS_FILE.exists():
        return []
    with onlypt.LEADS_FILE.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def read_traffic_events():
    if not onlypt.TRAFFIC_LOG_FILE.exists():
        return []
    return [
        json.loads(line)
        for line in onlypt.TRAFFIC_LOG_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_admin_can_block_and_unblock_contact_form_ip(client):
    response = client.post("/admin/api/contact-ip-blocks", json={"ip": "203.0.113.9", "blocked": True})

    assert response.status_code == 200
    assert response.get_json()["blocked"] is True
    blocks = json.loads(onlypt.CONTACT_IP_BLOCKS_FILE.read_text(encoding="utf-8"))
    assert "203.0.113.9" in blocks

    response = client.post("/admin/api/contact-ip-blocks", json={"ip": "203.0.113.9", "blocked": False})

    assert response.status_code == 200
    assert response.get_json()["blocked"] is False
    blocks = json.loads(onlypt.CONTACT_IP_BLOCKS_FILE.read_text(encoding="utf-8"))
    assert "203.0.113.9" not in blocks


def test_blocked_ip_cannot_submit_contact_form(client):
    client.post("/admin/api/contact-ip-blocks", json={"ip": "203.0.113.9", "blocked": True})

    response = post_contact(client, "203.0.113.9")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/contact")
    assert read_lead_rows() == []
    assert [event for event in read_traffic_events() if event.get("type") == "form_submission"] == []


def test_unblocked_ip_can_submit_contact_form(client):
    response = post_contact(client, "198.51.100.8")

    assert response.status_code == 302
    assert len(read_lead_rows()) == 1
    form_events = [event for event in read_traffic_events() if event.get("type") == "form_submission"]
    assert len(form_events) == 1
    assert form_events[0]["ip"] == "198.51.100.8"
