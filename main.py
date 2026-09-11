from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models import FridgeItem, NutritionNeeds, UserProfile, calculate_nutrition_needs


app = FastAPI(
	title="Smart Fridge & Nutrition Coach",
	description="API de coaching nutritionnel et de gestion d'un frigo intelligent.",
	version="0.1.0",
)

fridge_inventory: list[FridgeItem] = []

app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:3000", "http://localhost:8000"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


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
