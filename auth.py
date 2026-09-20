import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from supabase_auth.errors import AuthApiError

from database import connection, supabase_client, using_supabase

load_dotenv()

router = APIRouter(prefix="/auth", tags=["Account"])
bearer = HTTPBearer(auto_error=False)
# Used only by the local SQLite fallback. Supabase signs and validates its own sessions.
SECRET = os.getenv("JWT_SECRET") or secrets.token_hex(32)
if len(SECRET) < 32:
    raise RuntimeError("JWT_SECRET doit contenir au moins 32 caractères.")


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return salt + ":" + digest


def _local_token(user: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "access_token": jwt.encode(
            {"sub": str(user["id"]), "iat": now, "exp": now + timedelta(hours=2)},
            SECRET,
            algorithm="HS256",
        ),
        "token_type": "bearer",
        "email": user["email"],
    }


def session_token(session: Any) -> dict[str, Any]:
    """Return the browser session shape for either Supabase or SQLite."""
    if not using_supabase():
        return _local_token(session)
    if session is None:
        raise ValueError("Aucune session Supabase n'a été créée.")
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_in": session.expires_in,
        "token_type": "bearer",
        "email": session.user.email or "Visiteur",
        "demo": bool(session.user.is_anonymous),
    }


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            401,
            "Connectez-vous pour accéder à votre espace.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if using_supabase():
        try:
            auth_user = supabase_client().auth.get_user(credentials.credentials).user
            if auth_user is None or (not auth_user.email and not auth_user.is_anonymous):
                raise ValueError
            return {
                "id": auth_user.id,
                "email": auth_user.email or "Visiteur",
                "access_token": credentials.credentials,
            }
        except (AuthApiError, ValueError, TypeError):
            raise HTTPException(
                401,
                "Votre session Supabase est invalide ou expirée. Connectez-vous à nouveau.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "iat"]},
        )
        with connection() as db:
            user = db.execute(
                "SELECT id, email, profile FROM users WHERE id=?", (int(payload["sub"]),)
            ).fetchone()
        if user is None:
            raise ValueError
        return dict(user)
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(
            401,
            "Connectez-vous pour accéder à votre espace.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


@router.post("/register", status_code=201)
def register(data: Credentials):
    if using_supabase():
        try:
            response = supabase_client().auth.sign_up(
                {"email": str(data.email).lower(), "password": data.password}
            )
            if response.session is None:
                return {
                    "confirmation_required": True,
                    "email": str(data.email).lower(),
                }
            return session_token(response.session)
        except AuthApiError as exc:
            detail = (
                "Un compte utilise déjà cette adresse."
                if exc.status == 422
                else "Inscription impossible."
            )
            raise HTTPException(exc.status if exc.status < 500 else 502, detail) from exc
    try:
        with connection() as db:
            cursor = db.execute(
                "INSERT INTO users(email,password) VALUES (?,?)",
                (str(data.email).lower(), password_hash(data.password)),
            )
            return _local_token({"id": cursor.lastrowid, "email": str(data.email).lower()})
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Un compte utilise déjà cette adresse.") from None


@router.post("/login")
def login(data: Credentials):
    if using_supabase():
        try:
            response = supabase_client().auth.sign_in_with_password(
                {"email": str(data.email).lower(), "password": data.password}
            )
            return session_token(response.session)
        except AuthApiError as exc:
            raise HTTPException(
                401, "Adresse, mot de passe ou confirmation d’e-mail incorrect."
            ) from exc
    with connection() as db:
        user = db.execute(
            "SELECT * FROM users WHERE email=?", (str(data.email).lower(),)
        ).fetchone()
    encoded = user["password"] if user else password_hash("dummy-password")
    if (
        not hmac.compare_digest(password_hash(data.password, encoded.split(":")[0]), encoded)
        or not user
    ):
        raise HTTPException(401, "Adresse ou mot de passe incorrect.")
    return _local_token(user)


@router.post("/refresh")
def refresh_session(data: RefreshRequest):
    if not using_supabase():
        raise HTTPException(404, "Le renouvellement est géré par le mode Supabase uniquement.")
    try:
        response = supabase_client().auth.refresh_session(data.refresh_token)
        return session_token(response.session)
    except AuthApiError as exc:
        raise HTTPException(401, "Votre session a expiré. Connectez-vous à nouveau.") from exc


@router.get("/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, str]:
    return {"email": user["email"]}
