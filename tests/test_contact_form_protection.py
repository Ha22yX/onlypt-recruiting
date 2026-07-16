import csv

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
        yield test_client


def read_lead_rows():
    if not onlypt.LEADS_FILE.exists():
        return []
    with onlypt.LEADS_FILE.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def valid_form_data(**overrides):
    data = {
        "audience": "employer",
        "name": "Real Visitor",
        "email": "real@example.com",
        "organization": "Real Clinic",
        "phone": "5551234567",
        "role": "Clinic Director",
        "message": "I need help hiring a PT.",
    }
    data.update(overrides)
    return data


def seed_contact_challenge(client, started_at=1000.0, honeypot_name="company_website"):
    with client.session_transaction() as session:
        session["contact_form_token"] = "token-123"
        session["contact_form_started_at"] = started_at
        session["contact_honeypot_name"] = honeypot_name


def test_contact_post_without_session_token_is_rejected(client):
    response = client.post("/contact", data=valid_form_data())

    assert response.status_code == 302
    assert read_lead_rows() == []


def test_contact_post_with_filled_honeypot_is_rejected(client, monkeypatch):
    seed_contact_challenge(client)
    monkeypatch.setattr(onlypt, "now_timestamp", lambda: 1005.0)

    response = client.post(
        "/contact",
        data=valid_form_data(contact_form_token="token-123", company_website="https://spam.example"),
    )

    assert response.status_code == 302
    assert read_lead_rows() == []


def test_contact_post_too_fast_is_rejected(client, monkeypatch):
    seed_contact_challenge(client, started_at=1000.0)
    monkeypatch.setattr(onlypt, "now_timestamp", lambda: 1001.5)

    response = client.post("/contact", data=valid_form_data(contact_form_token="token-123"))

    assert response.status_code == 302
    assert read_lead_rows() == []


def test_contact_submission_records_request_metadata(client, monkeypatch):
    seed_contact_challenge(client, started_at=1000.0)
    monkeypatch.setattr(onlypt, "now_timestamp", lambda: 1003.0)

    response = client.post(
        "/contact",
        data=valid_form_data(contact_form_token="token-123"),
        headers={
            "X-Forwarded-For": "198.51.100.77",
            "User-Agent": "Test Browser",
            "Referer": "https://onlypt.co/contact",
        },
    )

    assert response.status_code == 302
    rows = read_lead_rows()
    assert len(rows) == 1
    assert rows[0]["ip"] == "198.51.100.77"
    assert rows[0]["user_agent"] == "Test Browser"
    assert rows[0]["referrer"] == "https://onlypt.co/contact"


def test_existing_leads_csv_is_migrated_before_metadata_write(client, monkeypatch):
    onlypt.LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)
    onlypt.LEADS_FILE.write_text(
        "created_at,audience,name,email,organization,phone,role,message\n"
        "2026-07-01T00:00:00+00:00,employer,Old Lead,old@example.com,Old Org,,,Old message\n",
        encoding="utf-8",
    )
    seed_contact_challenge(client, started_at=1000.0)
    monkeypatch.setattr(onlypt, "now_timestamp", lambda: 1003.0)

    client.post(
        "/contact",
        data=valid_form_data(contact_form_token="token-123"),
        headers={"X-Forwarded-For": "198.51.100.88", "User-Agent": "Migration Browser"},
    )

    rows = read_lead_rows()
    assert rows[0]["ip"] == ""
    assert rows[1]["ip"] == "198.51.100.88"
    assert "user_agent" in rows[0]
