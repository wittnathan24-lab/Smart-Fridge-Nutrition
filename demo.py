"""Deterministic portfolio fixtures, never represented as live USDA results."""

import secrets

from fastapi import APIRouter, HTTPException
from supabase_auth.errors import AuthApiError

from auth import password_hash, session_token
from config import get_settings
from database import create_item, get_profile, save_profile, supabase_client, using_supabase

router = APIRouter(tags=["Demo"])
RECIPES = [
    {
        "meal_id": "demo-1",
        "name": "Bowl de poulet, riz & brocoli",
        "category": "Équilibre",
        "ingredients": [
            {"name": "Poulet", "measure": "150 g"},
            {"name": "Riz cuit", "measure": "180 g"},
            {"name": "Brocoli", "measure": "150 g"},
        ],
        "instructions": "1. Faites cuire le riz selon les indications du paquet.\n2. Découpez le poulet et faites-le cuire à cœur dans une poêle.\n3. Faites cuire le brocoli à la vapeur.\n4. Assemblez le bowl et assaisonnez à votre goût.",
        "calories": 520,
        "protein": 48,
        "carbs": 57,
        "fat": 11,
    },
    {
        "meal_id": "demo-2",
        "name": "Salade de lentilles & tomates",
        "category": "Végétal",
        "ingredients": [
            {"name": "Lentilles cuites", "measure": "200 g"},
            {"name": "Tomates", "measure": "150 g"},
            {"name": "Huile d’olive", "measure": "10 g"},
        ],
        "instructions": "1. Rincez les lentilles cuites.\n2. Coupez les tomates en dés.\n3. Mélangez avec l’huile et les herbes de votre choix.",
        "calories": 360,
        "protein": 20,
        "carbs": 44,
        "fat": 12,
    },
    {
        "meal_id": "demo-3",
        "name": "Omelette verte & tartines",
        "category": "Express",
        "ingredients": [
            {"name": "Œufs", "measure": "120 g"},
            {"name": "Épinards", "measure": "100 g"},
            {"name": "Pain complet", "measure": "80 g"},
        ],
        "instructions": "1. Faites revenir les épinards.\n2. Battez les œufs et versez-les dans la poêle.\n3. Laissez cuire puis servez avec le pain grillé.",
        "calories": 420,
        "protein": 27,
        "carbs": 39,
        "fat": 18,
    },
]


@router.post("/auth/demo", status_code=201)
def demo():
    settings = get_settings()
    email = settings.demo_email
    profile = {
        "weight_kg": 70,
        "height_cm": 175,
        "age": 30,
        "sex": "female",
        "activity_level": "moderate",
        "goal": "maintenance",
    }
    password = secrets.token_urlsafe(32)
    if using_supabase():
        if not settings.demo_password or not settings.demo_user_id:
            raise HTTPException(503, "Le compte de démonstration n’est pas encore configuré.")
        try:
            response = supabase_client().auth.sign_in_with_password(
                {"email": email, "password": settings.demo_password}
            )
        except AuthApiError as exc:
            raise HTTPException(
                503,
                "La démonstration est momentanément indisponible. Connectez-vous à votre compte.",
            ) from exc
        if response.session is None:
            raise HTTPException(
                503,
                "La session de démonstration n'a pas pu être créée.",
            )
        payload = session_token(response.session)
        if response.user.id != settings.demo_user_id:
            raise HTTPException(503, "La configuration du compte de démonstration est invalide.")
        user = {
            "id": response.user.id,
            "email": response.user.email,
            "access_token": payload["access_token"],
        }
    else:
        from database import connection

        with connection() as db:
            db.execute(
                "INSERT OR IGNORE INTO users(email,password) VALUES (?,?)",
                (email, password_hash(password)),
            )
            user = dict(db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone())
        payload = session_token(user)
    if get_profile(user) is None:
        for name, quantity_g in [("Poulet", 300), ("Riz", 400), ("Brocoli", 250), ("Tomate", 300)]:
            create_item(user, name, quantity_g)
        save_profile(user, profile)
    return {**payload, "demo": True}
