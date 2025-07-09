from fastapi import APIRouter, HTTPException, status
from app.models.schemas import SignupRequest, LoginRequest, TokenResponse
from app.services.auth_service import hash_password, verify_password, create_access_token
from app.services.user_service import create_user, get_user_by_username

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/signup", response_model=TokenResponse)
def signup(payload: SignupRequest):
    existing = get_user_by_username(payload.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_pw = hash_password(payload.password)
    user = create_user(payload.username, payload.email, hashed_pw)

    token = create_access_token({"sub": payload.username})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    user = get_user_by_username(payload.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": payload.username})
    return TokenResponse(access_token=token)