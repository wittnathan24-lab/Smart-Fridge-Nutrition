from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from supabase_auth.errors import AuthApiError

import auth
from main import app
from middleware import attempts


@pytest.fixture
def supabase_auth(monkeypatch):
    attempts.clear()
    backend = Mock()
    monkeypatch.setattr(auth, "using_supabase", lambda: True)
    monkeypatch.setattr(auth, "supabase_client", lambda: SimpleNamespace(auth=backend))
    admin = Mock()
    admin.list_users.return_value = []
    monkeypatch.setattr(
        auth, "supabase_admin_client", lambda: SimpleNamespace(auth=SimpleNamespace(admin=admin))
    )
    return TestClient(app), backend


@pytest.mark.parametrize(
    "code,status,text",
    [
        ("email_not_confirmed", 403, "Confirmez votre adresse"),
        ("invalid_credentials", 401, "Adresse ou mot de passe"),
        ("over_email_send_rate_limit", 429, "limite"),
        ("email_address_not_authorized", 503, "pas encore configuré"),
        ("email_address_invalid", 422, "orthographe"),
    ],
)
def test_supabase_auth_errors_are_actionable(supabase_auth, code, status, text):
    client, backend = supabase_auth
    backend.sign_in_with_password.side_effect = AuthApiError("upstream message", 422, code)
    result = client.post("/auth/login", json={"email": "test@example.org", "password": "secret"})
    assert result.status_code == status
    assert text in result.json()["detail"]


def test_signup_requires_confirmation_without_creating_fake_session(supabase_auth):
    client, backend = supabase_auth
    backend.sign_up.return_value = SimpleNamespace(session=None, user=None)
    result = client.post(
        "/auth/register", json={"email": "test@example.org", "password": "test-password-123"}
    )
    assert result.status_code == 201
    assert result.json() == {"confirmation_required": True, "email": "test@example.org"}


def test_login_accepts_existing_short_password_but_registration_rejects_it(supabase_auth):
    client, backend = supabase_auth
    backend.sign_in_with_password.return_value = SimpleNamespace(
        session=SimpleNamespace(
            access_token="access",
            refresh_token="refresh",
            expires_in=3600,
            user=SimpleNamespace(id="test-user", email="test@example.org", is_anonymous=False),
        )
    )
    credentials = {"email": "test@example.org", "password": "secret"}
    assert client.post("/auth/login", json=credentials).status_code == 200
    assert client.post("/auth/register", json=credentials).status_code == 422


def test_resend_confirmation_uses_supabase_and_preserves_rate_limit(supabase_auth):
    client, backend = supabase_auth
    result = client.post("/auth/resend-confirmation", json={"email": "test@example.org"})
    assert result.status_code == 200
    backend.resend.assert_called_once_with({"type": "signup", "email": "test@example.org"})
    backend.resend.side_effect = AuthApiError("rate limited", 429, "over_email_send_rate_limit")
    assert (
        client.post("/auth/resend-confirmation", json={"email": "test@example.org"}).status_code
        == 429
    )


@pytest.mark.parametrize("confirmed", [None, "2026-09-21T12:00:00Z"])
def test_duplicate_signup_is_rejected(supabase_auth, confirmed):
    client, backend = supabase_auth
    auth.supabase_admin_client().auth.admin.list_users.return_value = [
        SimpleNamespace(email="TEST@example.org", email_confirmed_at=confirmed)
    ]
    result = client.post(
        "/auth/register", json={"email": "test@example.org", "password": "new-password-123"}
    )
    assert result.status_code == 409
    backend.sign_up.assert_not_called()


def test_duplicate_check_searches_all_pages(supabase_auth):
    client, backend = supabase_auth
    auth.supabase_admin_client().auth.admin.list_users.side_effect = [
        [SimpleNamespace(email=f"user{i}@example.org") for i in range(100)],
        [SimpleNamespace(email="test@example.org")],
    ]
    result = client.post(
        "/auth/register", json={"email": "test@example.org", "password": "new-password-123"}
    )
    assert result.status_code == 409
    backend.sign_up.assert_not_called()
