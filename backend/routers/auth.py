"""Authentication routes: register, login."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status, Header
from pydantic import BaseModel, EmailStr
import jwt
import backend.config as config
from backend.db.database import get_session
from backend.db.models import User, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def _create_token(user_id: str, email: str, is_admin: bool) -> str:
    """Create a JWT token."""
    expire = datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "email": email,
        "is_admin": is_admin,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest) -> AuthResponse:
    """Register a new user account."""
    if len(body.password) < 8:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password must be at least 8 characters")

    with get_session() as session:
        existing = session.query(User).filter(User.email == body.email.lower().strip()).first()
        if existing:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")

        # Bootstrap: if ADMIN_EMAIL + ADMIN_PASSWORD match, promote to admin on first registration
        is_admin = (
            config.ADMIN_EMAIL and
            config.ADMIN_PASSWORD and
            body.email.lower().strip() == config.ADMIN_EMAIL.lower() and
            body.password == config.ADMIN_PASSWORD
        )

        user = User(
            email=body.email.lower().strip(),
            password_hash=hash_password(body.password),
            is_admin=is_admin,
        )
        session.add(user)
        session.commit()
        user_id = user.id
        user_email = user.email
        user_data = {"id": user_id, "email": user_email, "is_admin": user.is_admin, "created_at": None}

    token = _create_token(user_id, user_email, user.is_admin)
    return AuthResponse(
        access_token=token,
        user=user_data,
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest) -> AuthResponse:
    """Login and receive a JWT token."""
    with get_session() as session:
        user = session.query(User).filter(User.email == body.email.lower().strip()).first()
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
        user_id = user.id
        user_email = user.email
        user_data = {"id": user_id, "email": user_email, "is_admin": user.is_admin, "created_at": None}

    token = _create_token(user_id, user_email, user.is_admin)
    return AuthResponse(
        access_token=token,
        user=user_data,
    )


@router.get("/me")
async def get_me(authorization: str = Header(None)) -> dict:
    """Return the currently authenticated user."""
    from backend.routers.dependencies import get_current_user
    user = get_current_user(authorization)
    return user.to_dict()
