import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    hashed = pwd_context.hash(password)
    logger.debug("Password hashed.")
    return hashed


def verify_password(plain_password: str, hashed_password: str) -> bool:
    valid = pwd_context.verify(plain_password, hashed_password)
    logger.debug("Password verified: %s", valid)
    return valid


def create_access_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    logger.debug("JWT token created.")
    return token


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print(hash_password("test123"))
    print(verify_password("test123", hash_password("test123")))
    print(create_access_token({"sub": "testuser"}))