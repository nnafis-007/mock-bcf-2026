import os
import time

from fastapi import FastAPI, HTTPException
from psycopg2.pool import SimpleConnectionPool

app = FastAPI()

pool: SimpleConnectionPool | None = None


def _create_pool() -> SimpleConnectionPool:
    return SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


@app.on_event("startup")
def startup() -> None:
    global pool

    # Docker compose `depends_on` doesn't guarantee DB readiness.
    # Create the pool on startup with retries so the container doesn't crash.
    max_attempts = int(os.getenv("DB_CONNECT_MAX_ATTEMPTS", "30"))
    delay_seconds = float(os.getenv("DB_CONNECT_DELAY_SECONDS", "1"))

    last_error: Exception | None = None
    for _ in range(max_attempts):
        try:
            pool = _create_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
            finally:
                pool.putconn(conn)
            return
        except Exception as exc:
            last_error = exc
            time.sleep(delay_seconds)

    # If DB never becomes ready, fail startup with a clear error.
    raise RuntimeError(f"Database not ready after {max_attempts} attempts: {last_error}")


@app.on_event("shutdown")
def shutdown() -> None:
    global pool
    if pool is not None:
        pool.closeall()
        pool = None

@app.get("/users")
def get_users():
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection pool not initialized")

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, name FROM users;")
            rows = cur.fetchall()
            return [{"id": r[0], "email": r[1], "name": r[2]} for r in rows]
    finally:
        pool.putconn(conn)
