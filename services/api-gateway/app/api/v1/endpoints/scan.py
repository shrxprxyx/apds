from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
import structlog

from app.core.database import get_db
from app.core.config import settings

router = APIRouter()
logger = structlog.get_logger()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── Schemas ──────────────────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


# ─── Helpers ──────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(user_id: str, email: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


# ─── Routes ───────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import text
    result = await db.execute(
        text("SELECT id, email, password_hash, role FROM users WHERE email = :email"),
        {"email": form_data.username},
    )
    user = result.fetchone()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_token(str(user.id), user.email, user.role)
    logger.info("user logged in", email=user.email)
    return TokenResponse(access_token=token)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import text

    # Check if email already exists
    result = await db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": payload.email},
    )
    if result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    hashed = hash_password(payload.password)
    await db.execute(
        text(
            "INSERT INTO users (email, password_hash, role) VALUES (:email, :hash, 'analyst')"
        ),
        {"email": payload.email, "hash": hashed},
    )
    await db.commit()
    logger.info("user registered", email=payload.email)
    return {"message": "Account created successfully"}


@router.get("/me")
async def me():
    # Placeholder — will add JWT dependency in next iteration
    return {"message": "auth working"}