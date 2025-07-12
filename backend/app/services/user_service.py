import logging
import psycopg2
from typing import Optional, Dict, Any
from psycopg2.extras import RealDictCursor
from app.core.config import settings

logger = logging.getLogger(__name__)

TABLE_CREATION_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    hashed_password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

def get_db_connection() -> psycopg2.extensions.connection:
    logger.debug("Connecting to DB...")
    return psycopg2.connect(settings.supabase_url, cursor_factory=RealDictCursor)


def init_user_table() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(TABLE_CREATION_SQL)
        conn.commit()
        logger.info("Ensured users table exists.")
    except Exception as e:
        logger.error("Table creation failed: %s", str(e))
        raise
    finally:
        cursor.close()
        conn.close()


def create_user(username: str, email: str, hashed_password: str) -> Dict[str, Any]:
    init_user_table()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (username, email, hashed_password)
            VALUES (%s, %s, %s)
            """,
            (username, email, hashed_password)
        )
        conn.commit()
        logger.info("User %s created.", username)
        return {"username": username, "email": email}
    except Exception as e:
        conn.rollback()
        logger.error("User creation failed: %s", str(e))
        raise
    finally:
        cursor.close()
        conn.close()


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    init_user_table()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()
        logger.info("User lookup for '%s': %s", username, "FOUND" if result else "NOT FOUND")
        return result
    except Exception as e:
        logger.error("User fetch failed: %s", str(e))
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print(create_user("testuser", "test@example.com", "hashed_pw_123"))
    print(get_user_by_username("testuser"))