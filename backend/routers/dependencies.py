"""FastAPI dependencies for auth."""
from fastapi import Header, HTTPException, status
import jwt
import backend.config as config
from backend.db.database import get_session
from backend.db.models import User
from typing import Optional


def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    """Extract and validate JWT from Authorization: Bearer *** header."""
    if not authorization:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing authorization header")

    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication scheme")
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authorization header")

    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
        # Detach from session so it survives after commit
        session.expunge(user)
        return user


def get_current_admin_user(authorization: Optional[str] = Header(None)) -> User:
    """Require the current user to be an admin."""
    user = get_current_user(authorization)
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
