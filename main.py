from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from models import FridgeItem, NutritionNeeds, UserProfile, calculate_nutrition_needs
from schemas import RecipeDetail, RecipeNutritionResult, RecipeSummary
from services.nutrition_aggregator import compute_recipe_nutrition
from services.themealdb import TheMealDBError, get_recipe_detail, search_recipes_by_ingredient
from services.usda import USDAError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
	async with httpx.AsyncClient() as client:
		app.state.http_client = client
		yield


app = FastAPI(
	title="Smart Fridge & Nutrition Coach",
	description="API de coaching nutritionnel et de gestion d'un frigo intelligent.",
	version="0.1.0",
	lifespan=lifespan,
)

fridge_inventory: list[FridgeItem] = []

app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:3000", "http://localhost:8000"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


def get_http_client(request: Request) -> httpx.AsyncClient:
	return request.app.state.http_client


@app.get("/", tags=["System"])
async def read_root() -> dict[str, str]:
	return {
		"name": "Smart Fridge & Nutrition Coach",
		"message": "API opérationnelle",
		"docs": "/docs",
	}


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
	return {"status": "ok"}


@app.post("/profile/nutrition", response_model=NutritionNeeds, tags=["Nutrition"])
async def calculate_profile_nutrition(profile: UserProfile) -> NutritionNeeds:
	return calculate_nutrition_needs(profile)


@app.post("/fridge/items", response_model=FridgeItem, status_code=201, tags=["Fridge"])
async def add_fridge_item(item: FridgeItem) -> FridgeItem:
	fridge_inventory.append(item)
	return item


@app.get("/fridge/items", response_model=list[FridgeItem], tags=["Fridge"])
async def list_fridge_items() -> list[FridgeItem]:
	return fridge_inventory


@app.get("/recipes/search", response_model=list[RecipeSummary], tags=["Recipes"])
async def search_recipes(
	ingredient: str, client: httpx.AsyncClient = Depends(get_http_client)
) -> list[RecipeSummary]:
	try:
		return await search_recipes_by_ingredient(client, ingredient)
	except TheMealDBError as exc:
		raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/recipes/{meal_id}", response_model=RecipeDetail, tags=["Recipes"])
async def get_recipe(
	meal_id: str, client: httpx.AsyncClient = Depends(get_http_client)
) -> RecipeDetail:
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


@app.get("/fridge/suggestions", response_model=list[RecipeSummary], tags=["Fridge"])
async def suggest_recipes_from_fridge(
	client: httpx.AsyncClient = Depends(get_http_client),
) -> list[RecipeSummary]:
	if not fridge_inventory:
		return []

	suggestions_by_meal_id: dict[str, RecipeSummary] = {}
	for item in fridge_inventory:
		try:
			matches = await search_recipes_by_ingredient(client, item.name)
		except TheMealDBError as exc:
			raise HTTPException(status_code=502, detail=str(exc)) from exc

		for recipe in matches:
			suggestions_by_meal_id[recipe.meal_id] = recipe

	return list(suggestions_by_meal_id.values())
