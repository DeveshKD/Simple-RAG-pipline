from fastapi import APIRouter
from ..services.auth_service import fastapi_users, auth_backend
from ..models.user_schemas import UserCreate, UserRead

router = APIRouter()

# provides /login, /logout
router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
)
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
)

# The /auth and /auth/jwt endpoints are managed by fastapi-users,
# using the components defined in auth_service.