from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import current_user
from database import create_meal, delete_meal, get_profile, list_meals, save_profile
from models import UserProfile, calculate_nutrition_needs

router = APIRouter(tags=["Personal space"], dependencies=[Depends(current_user)])


@router.get("/profile")
def get_user_profile(user: dict[str, Any] = Depends(current_user)):
    profile = get_profile(user)
    return {
        "profile": profile,
        "needs": calculate_nutrition_needs(UserProfile(**profile)) if profile else None,
    }


@router.put("/profile")
def save_user_profile(profile: UserProfile, user: dict[str, Any] = Depends(current_user)):
    save_profile(user, profile.model_dump())
    return calculate_nutrition_needs(profile)


class PlannedMeal(BaseModel):
    day: date
    name: str = Field(min_length=1, max_length=150)
    calories: float = Field(ge=0, le=10000, allow_inf_nan=False)
    protein: float = Field(ge=0, le=1000, allow_inf_nan=False)
    carbs: float = Field(ge=0, le=2000, allow_inf_nan=False)
    fat: float = Field(ge=0, le=1000, allow_inf_nan=False)


@router.get("/plan")
def plan(day: date, user: dict[str, Any] = Depends(current_user)):
    return list_meals(user, day)


@router.post("/plan", status_code=201)
def add_meal(meal: PlannedMeal, user: dict[str, Any] = Depends(current_user)):
    return create_meal(user, meal.model_dump())


@router.delete("/plan/{meal_id}")
def remove_meal(meal_id: int, user: dict[str, Any] = Depends(current_user)):
    if not delete_meal(user, meal_id):
        raise HTTPException(404, "Repas introuvable.")
    return {"deleted": True}
