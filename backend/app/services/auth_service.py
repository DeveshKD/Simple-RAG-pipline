import uuid
from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin, FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.orm import Session

from ..core.config import settings
from ..database import get_db
from ..models.db_models import User


SECRET = settings.secret_key

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """Manages user operations like registration, password resets, etc."""
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")



# Define the transport for tokens (Bearer tokens in the Auth header)
bearer_transport = BearerTransport(tokenUrl="/api/v2/auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    """Returns the JWT strategy with our secret and token lifetime."""
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

# combines the transport and strategy
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# dependincies
def _get_user_db(db: Session = Depends(get_db)):
    """Dependency to get the user database adapter."""
    yield SQLAlchemyUserDatabase(db, User)

async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(_get_user_db)):
    """Dependency to get the UserManager."""
    yield UserManager(user_db)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

# get current active user.
current_active_user = fastapi_users.current_user(active=True)