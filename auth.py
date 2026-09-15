import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from database import connection

router = APIRouter(prefix='/auth', tags=['Account'])
bearer = HTTPBearer(auto_error=False)
# Set JWT_SECRET in production; a random development key invalidates tokens at restart.
SECRET = os.getenv('JWT_SECRET') or secrets.token_hex(32)

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return salt + ':' + digest

def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        if credentials is None:
            raise ValueError()
        payload = jwt.decode(credentials.credentials, SECRET, algorithms=['HS256'], options={'require': ['exp', 'sub', 'iat']})
        with connection() as db:
            user = db.execute('SELECT id, email, profile FROM users WHERE id=?', (int(payload['sub']),)).fetchone()
        if user is None:
            raise ValueError()
        return dict(user)
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(401, 'Connectez-vous pour accéder à votre espace.', headers={'WWW-Authenticate': 'Bearer'})

def token(user):
    now = datetime.now(timezone.utc)
    return {'access_token': jwt.encode({'sub': str(user['id']), 'iat': now, 'exp': now + timedelta(hours=2)}, SECRET, algorithm='HS256'), 'token_type': 'bearer', 'email': user['email']}

@router.post('/register', status_code=201)
def register(data: Credentials):
    try:
        with connection() as db:
            cursor = db.execute('INSERT INTO users(email,password) VALUES (?,?)', (str(data.email).lower(), password_hash(data.password)))
            return token({'id': cursor.lastrowid, 'email': str(data.email).lower()})
    except sqlite3.IntegrityError:
        raise HTTPException(409, 'Un compte utilise déjà cette adresse.')

@router.post('/login')
def login(data: Credentials):
    with connection() as db:
        user = db.execute('SELECT * FROM users WHERE email=?', (str(data.email).lower(),)).fetchone()
    encoded = user['password'] if user else password_hash('dummy-password')
    if not hmac.compare_digest(password_hash(data.password, encoded.split(':')[0]), encoded) or not user:
        raise HTTPException(401, 'Adresse ou mot de passe incorrect.')
    return token(user)

@router.get('/me')
def me(user=Depends(current_user)):
    return {'email': user['email']}
