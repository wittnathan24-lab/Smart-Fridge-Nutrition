import json
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from auth import current_user
from database import connection
from models import UserProfile, calculate_nutrition_needs

router = APIRouter(tags=['Personal space'], dependencies=[Depends(current_user)])

@router.get('/profile')
def get_profile(user=Depends(current_user)):
    profile = json.loads(user['profile']) if user['profile'] else None
    return {'profile': profile, 'needs': calculate_nutrition_needs(UserProfile(**profile)) if profile else None}

@router.put('/profile')
def save_profile(profile: UserProfile, user=Depends(current_user)):
    with connection() as db:
        db.execute('UPDATE users SET profile=? WHERE id=?', (profile.model_dump_json(), user['id']))
    return calculate_nutrition_needs(profile)

class PlannedMeal(BaseModel):
    day: date
    name: str = Field(min_length=1, max_length=150)
    calories: float = Field(ge=0, le=10000, allow_inf_nan=False)
    protein: float = Field(ge=0, le=1000, allow_inf_nan=False)
    carbs: float = Field(ge=0, le=2000, allow_inf_nan=False)
    fat: float = Field(ge=0, le=1000, allow_inf_nan=False)

@router.get('/plan')
def plan(day: date, user=Depends(current_user)):
    with connection() as db:
        return [dict(r) for r in db.execute('SELECT * FROM meals WHERE user_id=? AND day=? ORDER BY id', (user['id'], str(day)))]

@router.post('/plan', status_code=201)
def add_meal(meal: PlannedMeal, user=Depends(current_user)):
    with connection() as db:
        cursor = db.execute('INSERT INTO meals(user_id,day,name,calories,protein,carbs,fat) VALUES (?,?,?,?,?,?,?)', (user['id'], str(meal.day), meal.name, meal.calories, meal.protein, meal.carbs, meal.fat))
        return {'id': cursor.lastrowid, **meal.model_dump()}

@router.delete('/plan/{meal_id}')
def delete_meal(meal_id: int, user=Depends(current_user)):
    with connection() as db:
        if not db.execute('DELETE FROM meals WHERE id=? AND user_id=?', (meal_id, user['id'])).rowcount:
            raise HTTPException(404, 'Repas introuvable.')
    return {'deleted': True}
