import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from auth import SECRET
from database import connection
from main import app
from models import UserProfile, calculate_nutrition_needs
from schemas import IngredientNutritionResult, NutrientProfile, RecipeDetail, USDAFoodMatch
from services.nutrition_aggregator import _parse_grams, _sum_estimated
from services.themealdb import TheMealDBError, search_recipes_by_ingredient
from services.usda import search_food


@pytest.fixture
def client(tmp_path, monkeypatch):
    from config import get_settings
    from middleware import attempts

    # Local tests must never create accounts or records in the configured cloud project.
    monkeypatch.setattr(get_settings(), "supabase_url", "")
    monkeypatch.setattr(get_settings(), "supabase_anon_key", "")
    attempts.clear()
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        yield client


def account(client, email="alice@example.org"):
    response = client.post(
        "/auth/register", json={"email": email, "password": "long-test-password"}
    )
    assert response.status_code == 201
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_account_lifecycle(client):
    headers = account(client)
    assert client.get("/auth/me", headers=headers).json() == {"email": "alice@example.org"}
    assert (
        client.post(
            "/auth/login", json={"email": "alice@example.org", "password": "wrong-password"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login", json={"email": "alice@example.org", "password": "long-test-password"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/auth/register", json={"email": "alice@example.org", "password": "long-test-password"}
        ).status_code
        == 409
    )
    with connection() as db:
        assert db.execute("SELECT password FROM users").fetchone()[0] != "long-test-password"


@pytest.mark.parametrize(
    "path",
    [
        "/fridge/items",
        "/fridge/suggestions",
        "/profile",
        "/plan?day=2026-09-15",
        "/recipes/123",
        "/recipes/123/nutrition",
    ],
)
def test_private_routes(client, path):
    assert client.get(path).status_code == 401


def test_token_expiry_and_tampering(client):
    headers = account(client)
    expired = jwt.encode(
        {
            "sub": "1",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        SECRET,
        algorithm="HS256",
    )
    for token in [expired, headers["Authorization"][7:] + "x"]:
        assert (
            client.get("/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401
        )


def test_inventory_isolation_and_crud(client):
    alice, bob = account(client), account(client, "bob@example.org")
    item = client.post(
        "/fridge/items", headers=alice, json={"name": "Poulet", "quantity_g": 200}
    ).json()
    assert client.get("/fridge/items", headers=bob).json() == []
    assert (
        client.put(
            "/fridge/items/" + str(item["id"]), headers=bob, json={"name": "Riz", "quantity_g": 1}
        ).status_code
        == 404
    )
    assert client.delete("/fridge/items/" + str(item["id"]), headers=bob).status_code == 404
    assert (
        client.put(
            "/fridge/items/" + str(item["id"]),
            headers=alice,
            json={"name": "Poulet", "quantity_g": 300},
        ).status_code
        == 200
    )
    assert client.get("/fridge/items", headers=alice).json()[0]["quantity_g"] == 300
    assert client.delete("/fridge/items/" + str(item["id"]), headers=alice).status_code == 200
    assert client.get("/fridge/items", headers=alice).json() == []


@pytest.mark.parametrize(
    "item",
    [
        {"name": "  ", "quantity_g": 1},
        {"name": "Riz", "quantity_g": -1},
        {"name": "Riz", "quantity_g": "NaN"},
    ],
)
def test_invalid_inventory(client, item):
    assert client.post("/fridge/items", headers=account(client), json=item).status_code == 422


def test_demo_profile_and_persistent_plan(client):
    demo = client.post("/auth/demo").json()
    headers = {"Authorization": "Bearer " + demo["access_token"]}
    assert len(client.get("/fridge/items", headers=headers).json()) == 4
    profile = client.get("/profile", headers=headers).json()
    assert profile["needs"]["protein_g"] > 0
    data = {
        "day": "2026-09-15",
        "name": "Bowl",
        "calories": 520,
        "protein": 48,
        "carbs": 57,
        "fat": 11,
    }
    meal = client.post("/plan", headers=headers, json=data).json()
    assert len(client.get("/plan?day=2026-09-15", headers=headers).json()) == 1
    assert client.get("/plan?day=2026-09-16", headers=headers).json() == []
    bob = account(client)
    assert client.delete("/plan/" + str(meal["id"]), headers=bob).status_code == 404
    assert client.delete("/plan/" + str(meal["id"]), headers=headers).status_code == 200
    assert len(client.get("/recipes/demo-1", headers=headers).json()["ingredients"]) == 3


def test_metabolic_formula():
    p = UserProfile(
        weight_kg=70, height_cm=175, age=30, sex="male", activity_level="moderate", goal="loss"
    )
    n = calculate_nutrition_needs(p)
    assert n.bmr_kcal == 1648.75
    assert n.target_calories_kcal == 2055.56
    assert abs(n.protein_g * 4 + n.carbs_g * 4 + n.fat_g * 9 - n.target_calories_kcal) < 2


@pytest.mark.parametrize(
    "measure,expected",
    [
        ("200 g", 200),
        ("1,5 kg", 1500),
        ("1.5kg", 1500),
        ("1/2 kg", None),
        ("1-2 g", None),
        ("-5 g", None),
        ("1 cup", None),
        (".. g", None),
        (None, None),
    ],
)
def test_quantity_parser(measure, expected):
    assert _parse_grams(measure) == expected


def test_unknown_is_not_zero():
    assert _sum_estimated([]).calories_kcal is None
    assert (
        _sum_estimated(
            [
                IngredientNutritionResult(
                    ingredient="x", estimated_nutrients=NutrientProfile(calories_kcal=0)
                )
            ]
        ).calories_kcal
        == 0
    )


def test_external_shapes():
    recipe = RecipeDetail.model_validate(
        {
            "idMeal": "1",
            "strMeal": "Test",
            "strIngredient1": " Rice ",
            "strMeasure1": "200 g",
            "strIngredient2": "  ",
        }
    )
    assert recipe.ingredients[0].name == "Rice"
    assert RecipeDetail.model_validate(recipe.model_dump()).ingredients == recipe.ingredients
    food = USDAFoodMatch.model_validate(
        {
            "fdcId": 1,
            "description": "rice",
            "foodNutrients": [{"nutrientId": 1003, "value": 7}, {"nutrientId": 1008, "value": 300}],
        }
    )
    assert food.nutrients.protein_g == 7 and food.nutrients.carbs_g is None


@pytest.mark.parametrize("status", [429, 500])
def test_provider_errors(status):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(status))
        ) as c:
            with pytest.raises(TheMealDBError):
                await search_recipes_by_ingredient(c, "rice")

    asyncio.run(run())


def test_usda_filter(monkeypatch):
    from config import get_settings

    monkeypatch.setattr(get_settings(), "usda_api_key", "test-key")
    import json

    def handler(request):
        assert request.method == "POST"
        assert json.loads(request.content)["dataType"] == ["SR Legacy", "Foundation"]
        return httpx.Response(200, json={"foods": []})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            assert await search_food(c, "rice") is None

    asyncio.run(run())


def test_home_and_openapi(client):
    assert client.get("/").status_code == 200
    assert client.get("/static/tailwind.css").status_code == 200
    assert "/auth/register" in client.get("/openapi.json").json()["paths"]


def test_generate_day(client):
    demo = client.post("/auth/demo").json()
    headers = {"Authorization": "Bearer " + demo["access_token"]}
    assert client.post("/plan/generate?day=2026-09-15", headers=headers).status_code == 200
    meals = client.get("/plan?day=2026-09-15", headers=headers).json()
    assert len(meals) == 3
    target = client.get("/profile", headers=headers).json()["needs"]["target_calories_kcal"]
    assert abs(sum(m["calories"] for m in meals) - target) < 0.1
    assert client.post("/plan/generate?day=2026-09-15", headers=headers).status_code == 409


def test_auth_throttle(client):
    for _ in range(20):
        client.post("/auth/login", json={})
    assert client.post("/auth/login", json={}).status_code == 429


def test_network_failure():
    def handler(request):
        raise httpx.ConnectError("offline", request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            with pytest.raises(TheMealDBError):
                await search_recipes_by_ingredient(c, "rice")

    asyncio.run(run())


@pytest.mark.parametrize("payload", [[], {"meals": [{"wrong": "shape"}]}])
def test_malformed_provider_data(payload):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
        ) as c:
            with pytest.raises(TheMealDBError):
                await search_recipes_by_ingredient(c, "rice")

    asyncio.run(run())


def test_profile_survives_app_restart(client):
    headers = account(client)
    profile = dict(
        weight_kg=70,
        height_cm=175,
        age=30,
        sex="male",
        activity_level="moderate",
        goal="maintenance",
    )
    assert client.put("/profile", headers=headers, json=profile).status_code == 200
    with TestClient(app) as restarted:
        assert restarted.get("/profile", headers=headers).json()["profile"] == profile


def test_suggestions_rank_and_survive_partial_failure(client, monkeypatch):
    from schemas import RecipeSummary

    headers = account(client)
    for name in ["rice", "chicken", "tomato"]:
        client.post("/fridge/items", headers=headers, json={"name": name, "quantity_g": 100})

    async def search(client, ingredient):
        if ingredient == "tomato":
            raise TheMealDBError("offline")
        return [
            RecipeSummary(meal_id="shared", name="Shared"),
            RecipeSummary(meal_id=ingredient, name=ingredient),
        ]

    monkeypatch.setattr("main.search_recipes_by_ingredient", search)
    response = client.get("/fridge/suggestions", headers=headers)
    assert response.status_code == 200
    assert response.json()[0]["meal_id"] == "shared"
    assert len(response.json()) == 3


@pytest.mark.parametrize(
    "entered,expected",
    [
        ("  POuLET  ", "Poulet"),
        ("epinards", "Épinard"),
        ("oeufs", "Œuf"),
        ("crème fraîche", "Crème fraîche"),
        ("chicken", "Poulet"),
        ("tomates", "Tomate"),
        ("boeuf hache", "Bœuf haché"),
    ],
)
def test_recognized_ingredients_are_canonical(client, entered, expected):
    response = client.post(
        "/fridge/items", headers=account(client), json={"name": entered, "quantity_g": 100}
    )
    assert response.status_code == 201
    assert response.json()["name"] == expected


def test_unknown_ingredient_rejected_on_create_and_update(client):
    headers = account(client)
    item = client.post(
        "/fridge/items", headers=headers, json={"name": "Poulet", "quantity_g": 100}
    ).json()
    invalid = {"name": "poullett inconnu", "quantity_g": 100}
    assert client.post("/fridge/items", headers=headers, json=invalid).status_code == 422
    assert (
        client.put("/fridge/items/" + str(item["id"]), headers=headers, json=invalid).status_code
        == 422
    )
    assert client.get("/fridge/items", headers=headers).json()[0]["name"] == "Poulet"


def test_catalogue_is_public_and_consistent(client):
    from services.ingredient_catalogue import canonical_name
    from services.ingredient_mapping import to_english

    response = client.get("/ingredients")
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) > 150
    assert len({e["name"] for e in entries}) == len(entries)
    for entry in entries:
        assert canonical_name(entry["name"]) == entry["name"]
        for alias in entry["aliases"]:
            assert canonical_name(alias) == entry["name"]
        assert to_english(entry["name"])


def test_supabase_client_forwards_the_user_session(monkeypatch):
    import database
    from config import get_settings

    class FakePostgrest:
        def __init__(self):
            self.access_token = None

        def auth(self, access_token):
            self.access_token = access_token

    class FakeClient:
        def __init__(self):
            self.postgrest = FakePostgrest()

    settings = get_settings()
    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "publishable-key")
    client = FakeClient()
    monkeypatch.setattr(database, "create_client", lambda *args, **kwargs: client)

    assert database.supabase_client("user-session") is client
    assert client.postgrest.access_token == "user-session"


def test_real_supabase_sdk_client_initialization(monkeypatch):
    from config import get_settings
    from database import supabase_client

    monkeypatch.setattr(get_settings(), "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(get_settings(), "supabase_anon_key", "publishable-key")
    client = supabase_client("user-session")
    assert client.options.persist_session is False
    assert client.options.auto_refresh_token is False
    assert client.postgrest.headers["Authorization"] == "Bearer user-session"


def test_supabase_migration_enables_rls_and_plan_transaction():
    migration = (
        Path(__file__).parents[1] / "supabase" / "migrations" / "202609180001_smart_fridge.sql"
    ).read_text(encoding="utf-8")
    for table in ["profiles", "fridge_items", "planned_meals"]:
        assert f"alter table public.{table} enable row level security" in migration
    assert "auth.uid()" in migration
    assert "create_meal_plan" in migration


@pytest.mark.parametrize("url,key", [("https://example.supabase.co", ""), ("", "key")])
def test_partial_supabase_configuration_never_falls_back_to_sqlite(monkeypatch, url, key):
    from config import get_settings
    from database import DatabaseError, using_supabase

    monkeypatch.setattr(get_settings(), "supabase_url", url)
    monkeypatch.setattr(get_settings(), "supabase_anon_key", key)
    with pytest.raises(DatabaseError, match="Configuration Supabase incomplète"):
        using_supabase()


def test_demo_reuses_account_and_does_not_reset_inventory(client):
    first = client.post("/auth/demo").json()
    headers = {"Authorization": "Bearer " + first["access_token"]}
    for item in client.get("/fridge/items", headers=headers).json():
        assert client.delete(f"/fridge/items/{item['id']}", headers=headers).status_code == 200
    second = client.post("/auth/demo").json()
    second_headers = {"Authorization": "Bearer " + second["access_token"]}
    assert client.get("/fridge/items", headers=second_headers).json() == []
    with connection() as db:
        assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 1
