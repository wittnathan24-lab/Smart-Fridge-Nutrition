"""Explicit live check: creates two isolated demo guests in the configured project.

Run from the repository root: python -m scripts.check_supabase
Never prints tokens or keys. Guest accounts and demo data remain for inspection.
"""

from datetime import date

from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from database import DuplicatePlanError, create_generated_plan, supabase_client, using_supabase
from main import app


def check():
    assert using_supabase(), "Configure SUPABASE_URL and SUPABASE_ANON_KEY first."
    with TestClient(app) as client:
        sessions = []
        for _ in range(2):
            response = client.post("/auth/demo")
            assert response.status_code == 201, response.text
            sessions.append(response.json())
        first, second = sessions
        headers = {"Authorization": "Bearer " + first["access_token"]}
        other_headers = {"Authorization": "Bearer " + second["access_token"]}
        assert client.get("/auth/me", headers=headers).status_code == 200
        assert client.get("/profile", headers=headers).json()["profile"]["age"] == 30
        item = client.post(
            "/fridge/items", headers=headers, json={"name": "tomates", "quantity_g": 123}
        )
        assert item.status_code == 201, item.text
        item_id = item.json()["id"]
        path = f"/fridge/items/{item_id}"
        assert (
            client.put(
                path, headers=headers, json={"name": "Tomate", "quantity_g": 456}
            ).status_code
            == 200
        )
        assert any(
            row["id"] == item_id and float(row["quantity_g"]) == 456
            for row in client.get("/fridge/items", headers=headers).json()
        )
        assert not any(
            row["id"] == item_id
            for row in client.get("/fridge/items", headers=other_headers).json()
        )
        assert client.delete(path, headers=other_headers).status_code == 404
        first_id = supabase_client().auth.get_user(first["access_token"]).user.id
        try:
            supabase_client(second["access_token"]).table("fridge_items").insert(
                {"user_id": first_id, "name": "Tomate", "quantity_g": 10}
            ).execute()
        except APIError as exc:
            assert exc.code == "42501", str(exc)
        else:
            raise AssertionError("RLS allowed insertion into another user's fridge")
        assert supabase_client().table("fridge_items").select("id").execute().data == []
        user = {"id": first_id, "access_token": first["access_token"]}
        meal = {"name": "Repas test", "calories": 400, "protein": 20, "carbs": 50, "fat": 10}
        create_generated_plan(user, date.today(), [meal])
        try:
            create_generated_plan(user, date.today(), [meal])
        except DuplicatePlanError:
            pass
        else:
            raise AssertionError("Duplicate plan accepted")
        rows = client.get(f"/plan?day={date.today()}", headers=headers).json()
        assert len(rows) == 1 and rows[0]["name"] == meal["name"]
        assert client.get(f"/plan?day={date.today()}", headers=other_headers).json() == []
        refreshed = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()["demo"] is True
        refreshed_headers = {"Authorization": "Bearer " + refreshed.json()["access_token"]}
        assert client.get("/auth/me", headers=refreshed_headers).status_code == 200
        assert client.delete(path, headers=refreshed_headers).status_code == 200
        assert client.delete(f"/plan/{rows[0]['id']}", headers=refreshed_headers).status_code == 200
    print("PASS: Supabase sessions, refresh, profile, fridge CRUD, meal plan, RLS isolation.")
    print("Two guest accounts and their initial demo ingredients remain for inspection.")


if __name__ == "__main__":
    check()
