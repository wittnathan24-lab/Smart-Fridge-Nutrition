"""Provision the shared demo once; reruns reuse the existing account and data."""

import secrets

from dotenv import set_key

from config import get_settings
from database import supabase_admin_client


def setup():
    settings = get_settings()
    admin = supabase_admin_client().auth.admin
    page = 1
    found = None
    while True:
        users = admin.list_users(page=page, per_page=100)
        found = next((u for u in users if u.email == settings.demo_email), None)
        if found or len(users) < 100:
            break
        page += 1
    if found is None:
        password = settings.demo_password or secrets.token_urlsafe(48)
        set_key(".env", "DEMO_PASSWORD", password)
        found = admin.create_user(
            {"email": settings.demo_email, "password": password, "email_confirm": True}
        ).user
    elif not settings.demo_password:
        raise RuntimeError("Le compte existe mais son mot de passe serveur n'est pas configuré.")
    set_key(".env", "DEMO_USER_ID", found.id)
    get_settings.cache_clear()
    from demo import demo

    result = demo()
    assert result["demo"] is True
    print("Compte de démonstration configuré ; données existantes conservées.")


if __name__ == "__main__":
    setup()
