from pydantic import BaseModel, ConfigDict, Field, model_validator


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
