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

from config import get_settings
from database import connection, supabase_admin_client, supabase_client, using_supabase

load_dotenv()

router = APIRouter(prefix="/auth", tags=["Account"])
bearer = HTTPBearer(auto_error=False)
# Used only by the local SQLite fallback. Supabase signs and validates its own sessions.
SECRET = os.getenv("JWT_SECRET") or secrets.token_hex(32)
if len(SECRET) < 32:
    raise RuntimeError("JWT_SECRET doit contenir au moins 32 caractères.")


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class Registration(Credentials):
    password: str = Field(min_length=10, max_length=128)


class ConfirmationRequest(BaseModel):
    email: EmailStr


def auth_error(exc: AuthApiError) -> HTTPException:
    messages = {
        "email_not_confirmed": (
            403,
            "Confirmez votre adresse avec le lien reçu par e-mail avant de vous connecter. Vérifiez aussi les indésirables.",
        ),
        "invalid_credentials": (
            401,
            "Adresse ou mot de passe incorrect. Les anciens comptes locaux doivent être recréés sur Supabase.",
        ),
        "over_email_send_rate_limit": (
            429,
            "La limite d’envoi d’e-mails est atteinte. Patientez avant de demander un nouveau lien.",
        ),
        "over_request_rate_limit": (429, "Trop de tentatives. Patientez avant de réessayer."),
        "email_address_not_authorized": (
            503,
            "L’envoi de confirmations à cette adresse n’est pas encore configuré. Contactez le responsable de l’application.",
        ),
        "email_address_invalid": (
            422,
            "Cette adresse e-mail n’est pas acceptée. Vérifiez son orthographe.",
        ),
        "weak_password": (422, "Choisissez un mot de passe plus robuste d’au moins 10 caractères."),
        "user_already_exists": (409, "Un compte utilise déjà cette adresse. Connectez-vous."),
        "signup_disabled": (403, "Les inscriptions sont momentanément désactivées."),
    }
    status, detail = messages.get(
        exc.code,
        (
            502 if exc.status >= 500 else exc.status,
            "Authentification impossible. Réessayez dans un instant.",
        ),
    )
    return HTTPException(status, detail)


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
        "demo": bool(session.user.is_anonymous) or session.user.id == get_settings().demo_user_id,
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
                "demo": bool(auth_user.is_anonymous) or auth_user.id == get_settings().demo_user_id,
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
        return {**dict(user), "demo": user["email"] == get_settings().demo_email}
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(
            401,
            "Connectez-vous pour accéder à votre espace.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


@router.post("/register", status_code=201)
def register(data: Registration):
    if using_supabase():
        try:
            # Supabase's public signup deliberately masks existing confirmed accounts
            # and resends mail for unconfirmed accounts. Check server-side first.
            admin = supabase_admin_client().auth.admin
            page = 1
            while True:
                users = admin.list_users(page=page, per_page=100)
                if any((user.email or "").lower() == str(data.email).lower() for user in users):
                    raise HTTPException(
                        409,
                        "Un compte utilise déjà cette adresse. Connectez-vous ou renvoyez le lien de confirmation.",
                    )
                if len(users) < 100:
                    break
                page += 1
            response = supabase_client().auth.sign_up(
                {"email": str(data.email).lower(), "password": data.password}
            )
            if response.user is not None and response.user.identities == []:
                raise HTTPException(409, "Un compte utilise déjà cette adresse. Connectez-vous.")
            if response.session is None:
                return {
                    "confirmation_required": True,
                    "email": str(data.email).lower(),
                }
            return session_token(response.session)
        except AuthApiError as exc:
            raise auth_error(exc) from exc
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
            raise auth_error(exc) from exc
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


@router.post("/resend-confirmation")
def resend_confirmation(data: ConfirmationRequest):
    if not using_supabase():
        raise HTTPException(400, "La confirmation par e-mail n’est pas requise en mode local.")
    try:
        supabase_client().auth.resend({"type": "signup", "email": str(data.email).lower()})
    except AuthApiError as exc:
        raise auth_error(exc) from exc
    return {
        "message": "Si cette adresse attend une confirmation, un nouveau lien a été envoyé. Vérifiez aussi les indésirables."
    }


@router.get("/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, str]:
    return {"email": user["email"]}
