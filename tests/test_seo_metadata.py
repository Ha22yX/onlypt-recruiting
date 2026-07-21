import json
import re

import pytest

import app as onlypt


@pytest.fixture()
def client(tmp_path, monkeypatch):
    instance = tmp_path / "instance"
    monkeypatch.setattr(onlypt, "NOTIFICATIONS_LOG_FILE", instance / "notification_errors.log")
    monkeypatch.setattr(onlypt, "TRAFFIC_LOG_FILE", instance / "traffic_events.jsonl")
    monkeypatch.setattr(onlypt, "IP_REGION_CACHE_FILE", instance / "ip_region_cache.json")
    onlypt.app.config.update(TESTING=True)
    with onlypt.app.test_client() as test_client:
        yield test_client


def extract_json_ld(html: str) -> dict:
    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    assert match is not None
    return json.loads(match.group(1))


def test_home_seo_targets_employers_and_physical_therapists(client):
    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "<title>Physical Therapy Recruiting for Employers and PTs | onlyPT</title>" in html
    assert "physical therapy recruiting" in html
    assert "physical therapy jobs" in html
    assert '<meta property="og:image" content="https://onlypt.co/static/img/pt-recruiting-hero.png">' in html


def test_structured_data_describes_two_sided_recruiting_service(client):
    response = client.get("/therapists")
    data = extract_json_ld(response.get_data(as_text=True))
    graph = data["@graph"]
    agency = next(item for item in graph if "EmploymentAgency" in item["@type"])
    offer_names = [
        offer["itemOffered"]["name"]
        for offer in agency["makesOffer"]
    ]

    assert "Physical therapy recruiting" in agency["knowsAbout"]
    assert "Physical therapy jobs" in agency["knowsAbout"]
    assert "Physical Therapist recruiting for healthcare employers" in offer_names
    assert "Physical Therapy career matching for PT professionals" in offer_names


def test_sitemap_includes_public_pages_and_image_metadata(client):
    response = client.get("/sitemap.xml")
    xml = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "<loc>https://onlypt.co/</loc>" in xml
    assert "<loc>https://onlypt.co/employers</loc>" in xml
    assert "<loc>https://onlypt.co/therapists</loc>" in xml
    assert "<image:loc>https://onlypt.co/static/img/pt-recruiting-hero.png</image:loc>" in xml
