import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import settings


def get_db_connection():
    return psycopg2.connect(settings.supabase_url, cursor_factory=RealDictCursor)


def create_user(username: str, email: str, hashed_password: str):
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
    except Exception as e:
        conn.rollback()
        raise Exception(f"Error creating user: {e}")
    finally:
        cursor.close()
        conn.close()

    return {"username": username, "email": email}


def get_user_by_username(username: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT * FROM users WHERE username = %s",
            (username,)
        )
        user = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    return user