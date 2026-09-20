"""Persistence gateway for Supabase in production and SQLite during local development."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import Any

from supabase.lib.client_options import ClientOptions

from config import get_settings
from supabase import Client, create_client


class DatabaseError(Exception):
    """A database request could not be completed."""


class DuplicatePlanError(DatabaseError):
    """A day already has a generated plan."""


def using_supabase() -> bool:
    settings = get_settings()
    if bool(settings.supabase_url) != bool(settings.supabase_anon_key):
        raise DatabaseError(
            "Configuration Supabase incomplète : renseignez SUPABASE_URL et SUPABASE_ANON_KEY."
        )
    return bool(settings.supabase_url and settings.supabase_anon_key)


def supabase_client(access_token: str | None = None) -> Client:
    """Create a request-scoped client that keeps Supabase RLS active."""
    settings = get_settings()
    if not using_supabase():
        raise DatabaseError("Supabase n'est pas configuré.")
    client = create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )
    if access_token:
        client.postgrest.auth(access_token)
    return client


@contextmanager
def connection():
    """SQLite compatibility layer used only when Supabase is not configured."""
    db = sqlite3.connect(os.getenv("DATABASE_PATH", "smart_fridge.db"))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
        db.commit()
    finally:
        db.close()


def initialize() -> None:
    if using_supabase():
        return
    with connection() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, profile TEXT);
            CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), name TEXT NOT NULL, quantity_g REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS meals (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), day TEXT NOT NULL, name TEXT NOT NULL, calories REAL NOT NULL, protein REAL NOT NULL, carbs REAL NOT NULL, fat REAL NOT NULL);
            """
        )


def get_profile(user: dict[str, Any]) -> dict[str, Any] | None:
    if using_supabase():
        result = (
            supabase_client(user["access_token"])
            .table("profiles")
            .select("nutrition_profile")
            .eq("id", user["id"])
            .maybe_single()
            .execute()
        )
        return result.data["nutrition_profile"] if result.data else None
    return json.loads(user["profile"]) if user["profile"] else None


def save_profile(user: dict[str, Any], profile: dict[str, Any]) -> None:
    if using_supabase():
        (
            supabase_client(user["access_token"])
            .table("profiles")
            .upsert({"id": user["id"], "nutrition_profile": profile})
            .execute()
        )
        return
    with connection() as db:
        db.execute("UPDATE users SET profile=? WHERE id=?", (json.dumps(profile), user["id"]))


def list_items(user: dict[str, Any]) -> list[dict[str, Any]]:
    if using_supabase():
        result = (
            supabase_client(user["access_token"])
            .table("fridge_items")
            .select("id,name,quantity_g")
            .order("id")
            .execute()
        )
        return result.data
    with connection() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT id,name,quantity_g FROM items WHERE user_id=? ORDER BY id", (user["id"],)
            )
        ]


def create_item(user: dict[str, Any], name: str, quantity_g: float) -> dict[str, Any]:
    if using_supabase():
        result = (
            supabase_client(user["access_token"])
            .table("fridge_items")
            .insert({"user_id": user["id"], "name": name, "quantity_g": quantity_g})
            .execute()
        )
        return result.data[0]
    with connection() as db:
        cursor = db.execute(
            "INSERT INTO items(user_id,name,quantity_g) VALUES (?,?,?)",
            (user["id"], name, quantity_g),
        )
        return {"id": cursor.lastrowid, "name": name, "quantity_g": quantity_g}


def update_item(user: dict[str, Any], item_id: int, name: str, quantity_g: float) -> bool:
    if using_supabase():
        result = (
            supabase_client(user["access_token"])
            .table("fridge_items")
            .update({"name": name, "quantity_g": quantity_g})
            .eq("id", item_id)
            .select("id")
            .execute()
        )
        return bool(result.data)
    with connection() as db:
        return bool(
            db.execute(
                "UPDATE items SET name=?,quantity_g=? WHERE id=? AND user_id=?",
                (name, quantity_g, item_id, user["id"]),
            ).rowcount
        )


def delete_item(user: dict[str, Any], item_id: int) -> bool:
    if using_supabase():
        result = (
            supabase_client(user["access_token"])
            .table("fridge_items")
            .delete()
            .eq("id", item_id)
            .select("id")
            .execute()
        )
        return bool(result.data)
    with connection() as db:
        return bool(
            db.execute("DELETE FROM items WHERE id=? AND user_id=?", (item_id, user["id"])).rowcount
        )


def list_meals(user: dict[str, Any], meal_day: date) -> list[dict[str, Any]]:
    if using_supabase():
        result = (
            supabase_client(user["access_token"])
            .table("planned_meals")
            .select("id,day,name,calories,protein,carbs,fat")
            .eq("day", str(meal_day))
            .order("id")
            .execute()
        )
        return result.data
    with connection() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT * FROM meals WHERE user_id=? AND day=? ORDER BY id",
                (user["id"], str(meal_day)),
            )
        ]


def create_meal(user: dict[str, Any], meal: dict[str, Any]) -> dict[str, Any]:
    values = {"user_id": user["id"], **meal, "day": str(meal["day"])}
    if using_supabase():
        result = (
            supabase_client(user["access_token"]).table("planned_meals").insert(values).execute()
        )
        return result.data[0]
    with connection() as db:
        cursor = db.execute(
            "INSERT INTO meals(user_id,day,name,calories,protein,carbs,fat) VALUES (?,?,?,?,?,?,?)",
            (
                user["id"],
                values["day"],
                values["name"],
                values["calories"],
                values["protein"],
                values["carbs"],
                values["fat"],
            ),
        )
        return {"id": cursor.lastrowid, **meal}


def delete_meal(user: dict[str, Any], meal_id: int) -> bool:
    if using_supabase():
        result = (
            supabase_client(user["access_token"])
            .table("planned_meals")
            .delete()
            .eq("id", meal_id)
            .select("id")
            .execute()
        )
        return bool(result.data)
    with connection() as db:
        return bool(
            db.execute("DELETE FROM meals WHERE id=? AND user_id=?", (meal_id, user["id"])).rowcount
        )


def create_generated_plan(
    user: dict[str, Any], meal_day: date, meals: list[dict[str, Any]]
) -> None:
    payload = [{key: value for key, value in meal.items() if key != "day"} for meal in meals]
    if using_supabase():
        try:
            supabase_client(user["access_token"]).rpc(
                "create_meal_plan", {"p_day": str(meal_day), "p_meals": payload}
            ).execute()
        except Exception as exc:
            if "already exists" in str(exc).lower():
                raise DuplicatePlanError from exc
            raise DatabaseError("La création du plan Supabase a échoué.") from exc
        return
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute(
            "SELECT 1 FROM meals WHERE user_id=? AND day=?", (user["id"], str(meal_day))
        ).fetchone():
            raise DuplicatePlanError
        db.executemany(
            "INSERT INTO meals(user_id,day,name,calories,protein,carbs,fat) VALUES (?,?,?,?,?,?,?)",
            [
                (
                    user["id"],
                    str(meal_day),
                    meal["name"],
                    meal["calories"],
                    meal["protein"],
                    meal["carbs"],
                    meal["fat"],
                )
                for meal in meals
            ],
        )
