import asyncio
import re

import httpx

from schemas import (
    IngredientNutritionResult,
    IngredientQuantity,
    NutrientProfile,
    RecipeNutritionResult,
)
from services.ingredient_mapping import to_american_english
from services.themealdb import TheMealDBError, get_recipe_detail
from services.usda import USDAError, search_food

# Ne capture que les mesures explicitement en grammes/kilogrammes (ex: "200 g",
# "1.5kg"). TheMealDB donne surtout des mesures maison ("1 cup", "2 tbsp") que
# l'on ne peut pas convertir fiablement sans table de densites par ingredient :
# ces cas restent non extrapoles plutot que de produire un chiffre trompeur.
_GRAMS_PATTERN = re.compile(r"^\s*(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g)\s*$", re.IGNORECASE)


def _parse_grams(measure: str | None) -> float | None:
    match = _GRAMS_PATTERN.fullmatch(measure or "")
    if not match:
        return None
    value = float(match.group("value").replace(",", "."))
    return value * (1000 if match.group("unit").lower() == "kg" else 1) if value > 0 else None


def _scale(nutrients: NutrientProfile, grams: float) -> NutrientProfile:
    factor = grams / 100
    return NutrientProfile(
        calories_kcal=round(nutrients.calories_kcal * factor, 2)
        if nutrients.calories_kcal is not None
        else None,
        protein_g=round(nutrients.protein_g * factor, 2)
        if nutrients.protein_g is not None
        else None,
        carbs_g=round(nutrients.carbs_g * factor, 2) if nutrients.carbs_g is not None else None,
        fat_g=round(nutrients.fat_g * factor, 2) if nutrients.fat_g is not None else None,
    )


async def _lookup_ingredient_nutrition(
    client: httpx.AsyncClient, ingredient: IngredientQuantity
) -> IngredientNutritionResult:
    match = None
    try:
        match = await search_food(client, ingredient.name)
        if match is None:
            american_name = to_american_english(ingredient.name)
            if american_name:
                match = await search_food(client, american_name)
    except USDAError:
        # Un ingredient en echec ne doit pas faire tomber toute la recette :
        # il sera simplement remonte dans unmatched_ingredients.
        match = None

    if match is None:
        return IngredientNutritionResult(
            ingredient=ingredient.name, measure=ingredient.measure, matched=False
        )

    grams = _parse_grams(ingredient.measure)
    estimated = _scale(match.nutrients, grams) if grams is not None else None

    return IngredientNutritionResult(
        ingredient=ingredient.name,
        measure=ingredient.measure,
        matched=True,
        matched_food=match.description,
        nutrients_per_100g=match.nutrients,
        estimated_nutrients=estimated,
    )


def _sum_estimated(results: list[IngredientNutritionResult]) -> NutrientProfile:
    estimated = [r.estimated_nutrients for r in results if r.estimated_nutrients is not None]
    return NutrientProfile(
        **{
            field: round(sum(values), 2)
            if (values := [getattr(n, field) for n in estimated if getattr(n, field) is not None])
            else None
            for field in NutrientProfile.model_fields
        }
    )


async def compute_recipe_nutrition(
    client: httpx.AsyncClient, meal_id: str
) -> RecipeNutritionResult | None:
    try:
        recipe = await get_recipe_detail(client, meal_id)
    except TheMealDBError:
        raise

    if recipe is None:
        return None

    # Toutes les recherches USDA de la recette partent en parallele plutot
    # qu'en boucle sequentielle.
    results = await asyncio.gather(
        *[_lookup_ingredient_nutrition(client, ingredient) for ingredient in recipe.ingredients]
    )

    return RecipeNutritionResult(
        meal_id=recipe.meal_id,
        name=recipe.name,
        thumbnail=recipe.thumbnail,
        ingredients=list(results),
        unmatched_ingredients=[r.ingredient for r in results if not r.matched],
        estimated_total=_sum_estimated(list(results)),
    )
