import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from auth import current_user
from auth import router as auth_router
from database import connection, initialize
from demo import RECIPES
from demo import router as demo_router
from middleware import account_rate_limit
from models import FridgeItem, NutritionNeeds, UserProfile, calculate_nutrition_needs
from personal import router as personal_router
from schemas import RecipeDetail, RecipeNutritionResult, RecipeSummary
from services.ingredient_mapping import to_english
from services.nutrition_aggregator import compute_recipe_nutrition
from services.themealdb import TheMealDBError, get_recipe_detail, search_recipes_by_ingredient
from services.usda import USDAError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    initialize()
    async with httpx.AsyncClient() as client:
        app.state.http_client = client
        yield


app = FastAPI(
    title="Smart Fridge & Nutrition Coach",
    description="API de coaching nutritionnel et de gestion d'un frigo intelligent.",
    version="0.1.0",
    lifespan=lifespan,
)

app.middleware("http")(account_rate_limit)
app.include_router(auth_router)
app.include_router(demo_router)
app.include_router(personal_router)
BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


@app.get("/api", tags=["System"])
async def read_root() -> dict[str, str]:
    return {
        "name": "Smart Fridge & Nutrition Coach",
        "message": "API opérationnelle",
        "docs": "/docs",
    }


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/app", response_class=HTMLResponse, include_in_schema=False)
async def web_app(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="app.html")


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/profile/nutrition", response_model=NutritionNeeds, tags=["Nutrition"])
async def calculate_profile_nutrition(
    profile: UserProfile, user=Depends(current_user)
) -> NutritionNeeds:
    return calculate_nutrition_needs(profile)


@app.post("/fridge/items", status_code=201, tags=["Fridge"])
def add_fridge_item(item: FridgeItem, user=Depends(current_user)):
    with connection() as db:
        cursor = db.execute(
            "INSERT INTO items(user_id,name,quantity_g) VALUES (?,?,?)",
            (user["id"], item.name, item.quantity_g),
        )
        return {"id": cursor.lastrowid, **item.model_dump()}


@app.get("/fridge/items", tags=["Fridge"])
def list_fridge_items(user=Depends(current_user)):
    with connection() as db:
        return [
            dict(r)
            for r in db.execute(
                "SELECT id,name,quantity_g FROM items WHERE user_id=? ORDER BY id", (user["id"],)
            )
        ]


@app.put("/fridge/items/{item_id}", tags=["Fridge"])
def update_fridge_item(item_id: int, item: FridgeItem, user=Depends(current_user)):
    with connection() as db:
        if not db.execute(
            "UPDATE items SET name=?,quantity_g=? WHERE id=? AND user_id=?",
            (item.name, item.quantity_g, item_id, user["id"]),
        ).rowcount:
            raise HTTPException(404, "Ingrédient introuvable.")
    return {"id": item_id, **item.model_dump()}


@app.delete("/fridge/items/{item_id}", tags=["Fridge"])
def delete_fridge_item(item_id: int, user=Depends(current_user)):
    with connection() as db:
        if not db.execute(
            "DELETE FROM items WHERE id=? AND user_id=?", (item_id, user["id"])
        ).rowcount:
            raise HTTPException(404, "Ingrédient introuvable.")
    return {"deleted": True}


@app.get(
    "/recipes/search",
    response_model=list[RecipeSummary],
    response_model_by_alias=False,
    tags=["Recipes"],
    dependencies=[Depends(current_user)],
)
async def search_recipes(
    ingredient: str, client: httpx.AsyncClient = Depends(get_http_client)
) -> list[RecipeSummary]:
    try:
        return await search_recipes_by_ingredient(client, to_english(ingredient))
    except TheMealDBError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get(
    "/recipes/{meal_id}",
    response_model=RecipeDetail,
    response_model_by_alias=False,
    tags=["Recipes"],
    dependencies=[Depends(current_user)],
)
async def get_recipe(
    meal_id: str, client: httpx.AsyncClient = Depends(get_http_client)
) -> RecipeDetail:
    if meal_id.startswith("demo-"):
        data = next((r for r in RECIPES if r["meal_id"] == meal_id), None)
        if data is None:
            raise HTTPException(404, "Recette introuvable")
        return RecipeDetail.model_validate(data)
    try:
        recipe = await get_recipe_detail(client, meal_id)
    except TheMealDBError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if recipe is None:
        raise HTTPException(status_code=404, detail=f"Recette introuvable: {meal_id}")
    return recipe


@app.get(
    "/recipes/{meal_id}/nutrition",
    response_model=RecipeNutritionResult,
    tags=["Recipes"],
    dependencies=[Depends(current_user)],
)
async def get_recipe_nutrition(
    meal_id: str, client: httpx.AsyncClient = Depends(get_http_client)
) -> RecipeNutritionResult:
    try:
        result = await compute_recipe_nutrition(client, meal_id)
    except (TheMealDBError, USDAError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail=f"Recette introuvable: {meal_id}")
    return result


@app.get(
    "/fridge/suggestions",
    response_model=list[RecipeSummary],
    response_model_by_alias=False,
    tags=["Fridge"],
)
async def suggest_recipes_from_fridge(
    client: httpx.AsyncClient = Depends(get_http_client), user=Depends(current_user)
):
    items = list_fridge_items(user)
    ingredients = list(dict.fromkeys(to_english(item["name"]) for item in items))[:12]
    results = await asyncio.gather(
        *(search_recipes_by_ingredient(client, i) for i in ingredients), return_exceptions=True
    )
    if results and all(isinstance(r, Exception) for r in results):
        raise HTTPException(
            502, "Le service de recettes est indisponible. Réessayez dans quelques instants."
        )
    recipes, scores = {}, {}
    for result in results:
        if isinstance(result, Exception):
            continue
        for recipe in result:
            recipes[recipe.meal_id] = recipe
            scores[recipe.meal_id] = scores.get(recipe.meal_id, 0) + 1
    return sorted(recipes.values(), key=lambda r: (-scores[r.meal_id], r.name))[:18]


@app.get("/demo/recipes", dependencies=[Depends(current_user)], tags=["Demo"])
def demo_recipes():
    return RECIPES


@app.post("/plan/generate", tags=["Personal space"])
async def generate_plan(
    day: date, user=Depends(current_user), client: httpx.AsyncClient = Depends(get_http_client)
):
    import json

    from personal import PlannedMeal

    if not user["profile"]:
        raise HTTPException(422, "Enregistrez votre profil avant de composer une journée.")
    target = calculate_nutrition_needs(
        UserProfile(**json.loads(user["profile"]))
    ).target_calories_kcal
    if user["email"].endswith("@example.invalid"):
        candidates = RECIPES
    else:
        suggestions = await suggest_recipes_from_fridge(client, user)
        results = await asyncio.gather(
            *(compute_recipe_nutrition(client, r.meal_id) for r in suggestions[:3]),
            return_exceptions=True,
        )
        candidates = []
        for result in results:
            if isinstance(result, Exception) or result is None or not result.ingredients:
                continue
            if not all(
                i.estimated_nutrients
                and all(v is not None for v in i.estimated_nutrients.model_dump().values())
                for i in result.ingredients
            ):
                continue
            n = result.estimated_total
            candidates.append(
                {
                    "name": result.name,
                    "calories": n.calories_kcal,
                    "protein": n.protein_g,
                    "carbs": n.carbs_g,
                    "fat": n.fat_g,
                }
            )
    if len(candidates) < 3:
        raise HTTPException(
            422,
            "Trois recettes avec des apports complets sont nécessaires. Ajoutez des ingrédients ou utilisez la démonstration.",
        )
    meals = []
    for recipe, fraction in zip(candidates[:3], [0.30, 0.35, 0.35]):
        if recipe["calories"] <= 0:
            raise HTTPException(422, "Apports insuffisants pour calculer les portions.")
        scale = target * fraction / recipe["calories"]
        meal = PlannedMeal(
            day=day,
            name=recipe["name"],
            **{k: round(recipe[k] * scale, 2) for k in ["calories", "protein", "carbs", "fat"]},
        )
        meals.append(meal)
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute(
            "SELECT 1 FROM meals WHERE user_id=? AND day=?", (user["id"], str(day))
        ).fetchone():
            raise HTTPException(
                409, "Cette journée contient déjà des repas. Choisissez une journée vide."
            )
        for meal in meals:
            db.execute(
                "INSERT INTO meals(user_id,day,name,calories,protein,carbs,fat) VALUES (?,?,?,?,?,?,?)",
                (
                    user["id"],
                    str(day),
                    meal.name,
                    meal.calories,
                    meal.protein,
                    meal.carbs,
                    meal.fat,
                ),
            )
    return {
        "created": 3,
        "message": "Trois repas ajustés à votre cible énergétique. Les macros restent des repères à comparer.",
    }
