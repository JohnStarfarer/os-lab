import os
import time
import psycopg2
from psycopg2 import OperationalError


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def wait_for_db(max_retries=30, delay_seconds=2):
    """Ожидает готовности базы данных."""
    retries = 0
    while retries < max_retries:
        try:
            conn = get_connection()
            conn.close()
            print("✅ Database is available!")
            return True
        except OperationalError as e:
            print(f"⏳ Database not ready (attempt {retries+1}/{max_retries}): {e}")
            time.sleep(delay_seconds)
            retries += 1
    raise Exception("❌ Could not connect to the database after several retries")


def init_db():
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id SERIAL PRIMARY KEY,
                    text TEXT NOT NULL
                );
            """)
    conn.close()