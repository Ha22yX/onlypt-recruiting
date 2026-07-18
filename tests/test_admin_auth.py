from pathlib import Path

import app as onlypt


def test_admin_password_has_no_hardcoded_default():
    source = Path(onlypt.__file__).read_text(encoding="utf-8")
    leaked_default = "Only" + "PT" + "135"

    assert leaked_default not in source


def test_admin_login_is_disabled_without_configured_password(monkeypatch):
    monkeypatch.setattr(onlypt, "ADMIN_PASSWORD", "")
    onlypt.app.config.update(TESTING=True, SECRET_KEY="test-secret")

    with onlypt.app.test_client() as client:
        response = client.post(
            "/admin/login",
            data={"username": onlypt.ADMIN_USERNAME, "password": ""},
        )

        assert response.status_code == 200
        with client.session_transaction() as session_data:
            assert not session_data.get("admin_authenticated")
