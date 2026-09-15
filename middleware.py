"""Small single-process abuse guard for account endpoints."""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import Request
from fastapi.responses import JSONResponse

attempts = defaultdict(deque)
lock = Lock()


async def account_rate_limit(request: Request, call_next):
    if request.method == "POST" and request.url.path.startswith("/auth/"):
        key = request.client.host if request.client else "unknown"
        now = monotonic()
        with lock:
            for address in list(attempts):
                while attempts[address] and attempts[address][0] <= now - 60:
                    attempts[address].popleft()
                if not attempts[address]:
                    del attempts[address]
            if len(attempts[key]) >= 20:
                return JSONResponse(
                    {"detail": "Trop de tentatives. Réessayez dans une minute."},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
            attempts[key].append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith(("/auth", "/profile", "/fridge", "/plan")):
        response.headers["Cache-Control"] = "no-store"
    return response
