from fastapi import Request, HTTPException
from .auth_config import JWT_SECRET_ENV_VAR, JWT_ALGORITHM

def require_auth(request: Request):
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
