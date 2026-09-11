from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Sex(StrEnum):
    MALE = "male"
    FEMALE = "female"


class ActivityLevel(StrEnum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class Goal(StrEnum):
    LOSS = "loss"
    MAINTENANCE = "maintenance"
    GAIN = "gain"


class UserProfile(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    weight_kg: float = Field(gt=0, le=500)
    height_cm: float = Field(gt=0, le=300)
    age: int = Field(ge=13, le=120)
    sex: Sex
    activity_level: ActivityLevel
    goal: Goal


class NutritionNeeds(BaseModel):
    bmr_kcal: float
    tdee_kcal: float
    target_calories_kcal: float


class FridgeItem(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    quantity_g: float = Field(gt=0, le=100000)


ACTIVITY_FACTORS = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.HIGH: 1.725,
    ActivityLevel.VERY_HIGH: 1.9,
}

GOAL_DELTAS = {
    Goal.LOSS: -500,
    Goal.MAINTENANCE: 0,
    Goal.GAIN: 300,
}


def calculate_nutrition_needs(profile: UserProfile) -> NutritionNeeds:
    sex_offset = 5 if profile.sex == Sex.MALE else -161
    bmr = (10 * profile.weight_kg) + (6.25 * profile.height_cm) - (5 * profile.age) + sex_offset
    tdee = bmr * ACTIVITY_FACTORS[profile.activity_level]
    target_calories = tdee + GOAL_DELTAS[profile.goal]

    return NutritionNeeds(
        bmr_kcal=round(bmr, 2),
        tdee_kcal=round(tdee, 2),
        target_calories_kcal=round(target_calories, 2),
    )
