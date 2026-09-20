from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt as _bcrypt
from pydantic import BaseModel

from database import get_db
from models.user import User, UserRole
from models.password_reset import PasswordReset
from services.password_reset import consume_reset_token, hash_reset_token, reset_mode
from config import get_settings

router = APIRouter()
settings = get_settings()

def _hash_pw(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

def _verify_pw(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str


class UserCreate(BaseModel):
    email: str
    password: str
    role: UserRole = UserRole.viewer


def create_access_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({**data, "exp": expire}, settings.secret_key, algorithm=settings.algorithm)


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        email: str = payload.get("sub")
        if not email:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not _verify_pw(form.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    user.last_login = datetime.utcnow()
    await db.commit()

    token = create_access_token({"sub": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role}


@router.post("/users", status_code=201)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=data.email, password_hash=_hash_pw(data.password), role=data.role)
    db.add(user)
    await db.commit()
    return {"id": str(user.id), "email": user.email, "role": user.role}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {"id": str(current_user.id), "email": current_user.email, "role": current_user.role}


class ForgotRequest(BaseModel):
    email: str


class ResetRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot")
async def forgot_password(body: ForgotRequest, db: AsyncSession = Depends(get_db)):
    """Never says whether the address exists. Tells the page how resets work on this
    install: by a link the server operator creates (`manage_users.py reset-link`) —
    mail is not something the free product can assume it has."""
    return {"ok": True, "mode": reset_mode()}


@router.post("/reset")
async def reset_password(body: ResetRequest, db: AsyncSession = Depends(get_db)):
    if len(body.new_password) < 10:
        raise HTTPException(status_code=400, detail="Use at least 10 characters")
    user = await consume_reset_token(db, body.token)
    if user is None:
        raise HTTPException(status_code=400, detail="This reset link is not valid any more. Ask for a new one.")
    user.password_hash = _hash_pw(body.new_password)
    await db.commit()
    return {"ok": True, "email": user.email}
