"""Live check: reuses the shared demo, creates no account, prints no secrets."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from config import get_settings
from database import supabase_client, using_supabase
from main import app


def check():
    assert using_supabase(), "Configure Supabase first."
    settings = get_settings()
    with TestClient(app) as client:
        sessions = []
        for _ in range(2):
            response = client.post("/auth/demo")
            assert response.status_code == 201, response.text
            sessions.append(response.json())
        first, second = sessions
        for session in sessions:
            user = supabase_client().auth.get_user(session["access_token"]).user
            assert user.id == settings.demo_user_id and not user.is_anonymous
        headers = {"Authorization": "Bearer " + first["access_token"]}
        other_headers = {"Authorization": "Bearer " + second["access_token"]}
        login = client.post(
            "/auth/login",
            json={
                "email": settings.demo_email,
                "password": settings.demo_password,
            },
        )
        assert login.status_code == 200 and login.json()["demo"] is True
        duplicate = client.post(
            "/auth/register",
            json={
                "email": settings.demo_email,
                "password": "should-not-change-password-123",
            },
        )
        assert duplicate.status_code == 409, duplicate.text
        assert client.get("/profile", headers=headers).json()["profile"] is not None
        response = client.post(
            "/fridge/items", headers=headers, json={"name": "Carotte", "quantity_g": 123}
        )
        assert response.status_code == 201, response.text
        item_id = response.json()["id"]
        meal_ids = []
        try:
            assert (
                client.put(
                    f"/fridge/items/{item_id}",
                    headers=headers,
                    json={"name": "Carotte", "quantity_g": 456},
                ).status_code
                == 200
            )
            assert any(
                row["id"] == item_id
                for row in client.get("/fridge/items", headers=other_headers).json()
            )
            assert supabase_client().table("fridge_items").select("id").execute().data == []
            meal_day = date(2099, 1, 1)
            while client.get(f"/plan?day={meal_day}", headers=headers).json():
                meal_day += timedelta(days=1)
            generated = client.post(f"/plan/generate?day={meal_day}", headers=headers)
            assert generated.status_code == 200, generated.text
            meal_ids = [
                row["id"] for row in client.get(f"/plan?day={meal_day}", headers=headers).json()
            ]
            assert len(meal_ids) == 3
            assert client.post(f"/plan/generate?day={meal_day}", headers=headers).status_code == 409
            refreshed = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
            assert refreshed.status_code == 200 and refreshed.json()["demo"] is True
        finally:
            assert (
                client.delete(f"/fridge/items/{item_id}", headers=other_headers).status_code == 200
            )
            for meal_id in meal_ids:
                assert client.delete(f"/plan/{meal_id}", headers=other_headers).status_code == 200
    print(
        "PASS: shared demo reused, password login, duplicate signup denied, persistent fridge, generated meals, refresh."
    )


if __name__ == "__main__":
    check()
