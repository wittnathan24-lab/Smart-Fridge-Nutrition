from pydantic import BaseModel, ConfigDict, Field, model_validator

# Identifiants officiels USDA FoodData Central (foodNutrients[].nutrientId)
USDA_NUTRIENT_ID_ENERGY = 1008
USDA_NUTRIENT_ID_PROTEIN = 1003
USDA_NUTRIENT_ID_FAT = 1004
USDA_NUTRIENT_ID_CARBS = 1005


class IngredientQuantity(BaseModel):
    name: str
    measure: str | None = None


class RecipeSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    meal_id: str = Field(alias="idMeal")
    name: str = Field(alias="strMeal")
    thumbnail: str | None = Field(default=None, alias="strMealThumb")


class RecipeDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    meal_id: str = Field(alias="idMeal")
    name: str = Field(alias="strMeal")
    category: str | None = Field(default=None, alias="strCategory")
    area: str | None = Field(default=None, alias="strArea")
    instructions: str | None = Field(default=None, alias="strInstructions")
    thumbnail: str | None = Field(default=None, alias="strMealThumb")
    ingredients: list[IngredientQuantity] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def flatten_ingredients(cls, data: dict) -> dict:
        """TheMealDB eparpille les ingredients sur 20 paires de cles
        (strIngredient1/strMeasure1 ... strIngredient20/strMeasure20) au lieu
        d'un tableau. On les aplatit ici en liste avant toute autre validation.
        """
        if not isinstance(data, dict):
            return data

        ingredients = []
        for i in range(1, 21):
            name = data.get(f"strIngredient{i}")
            if name and name.strip():
                measure = (data.get(f"strMeasure{i}") or "").strip() or None
                ingredients.append({"name": name.strip(), "measure": measure})

        return {**data, "ingredients": ingredients}


class NutrientProfile(BaseModel):
    """Valeurs pour 100g, extraites par identifiant officiel USDA."""

    calories_kcal: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None


class USDAFoodMatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    fdc_id: int = Field(alias="fdcId")
    description: str
    data_type: str | None = Field(default=None, alias="dataType")
    nutrients: NutrientProfile = Field(default_factory=NutrientProfile)

    @model_validator(mode="before")
    @classmethod
    def extract_key_nutrients(cls, data: dict) -> dict:
        """foodNutrients est une liste non ordonnee de {nutrientId, value, ...}.
        On indexe par nutrientId plutot que par position pour extraire
        l'energie (1008) et les trois macros (1003, 1004, 1005).
        """
        if not isinstance(data, dict):
            return data

        values_by_nutrient_id = {
            nutrient.get("nutrientId"): nutrient.get("value")
            for nutrient in data.get("foodNutrients", [])
            if nutrient.get("nutrientId") is not None
        }

        nutrients = {
            "calories_kcal": values_by_nutrient_id.get(USDA_NUTRIENT_ID_ENERGY),
            "protein_g": values_by_nutrient_id.get(USDA_NUTRIENT_ID_PROTEIN),
            "carbs_g": values_by_nutrient_id.get(USDA_NUTRIENT_ID_CARBS),
            "fat_g": values_by_nutrient_id.get(USDA_NUTRIENT_ID_FAT),
        }

        return {**data, "nutrients": nutrients}
