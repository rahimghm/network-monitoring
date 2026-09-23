"""
Authentification JWT + RBAC (Admin / Technician / Supervisor).

Bootstrap : tant qu'aucun utilisateur n'existe en base, POST /auth/register
est ouvert et crée le premier compte en tant qu'Admin. Une fois au moins un
utilisateur créé, seul un Admin authentifié peut en créer d'autres.
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from .database import get_cursor

SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8h

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

ROLES = ("admin", "technician", "supervisor")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decode_token(token)
    username = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=401, detail="Token invalide")
    with get_cursor() as cur:
        cur.execute("SELECT id, username, role FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
    if user is None:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return user


def require_role(*allowed_roles: str):
    """Dépendance FastAPI : Depends(require_role('admin', 'technician'))"""
    def _guard(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rôle requis : {', '.join(allowed_roles)}"
            )
        return user
    return _guard


def users_exist() -> bool:
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS count FROM users")
        return cur.fetchone()["count"] > 0
