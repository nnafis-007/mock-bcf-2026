import os
import time
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from psycopg2 import IntegrityError
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor

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


def _require_pool() -> SimpleConnectionPool:
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection pool not initialized")
    return pool


def _parse_positive_int(value: Any, field_name: str) -> int:
    try:
        parsed = int(value)
    except Exception:
        raise HTTPException(status_code=400, detail=f"{field_name} must be an integer")
    if parsed <= 0:
        raise HTTPException(status_code=400, detail=f"{field_name} must be positive")
    return parsed


def _parse_non_negative_int(value: Any, field_name: str) -> int:
    try:
        parsed = int(value)
    except Exception:
        raise HTTPException(status_code=400, detail=f"{field_name} must be an integer")
    if parsed < 0:
        raise HTTPException(status_code=400, detail=f"{field_name} must be non-negative")
    return parsed


REDEMPTION_COFFEE_ID = "00000000-0000-0000-0000-000000000000"


class CreateCoffeeRequest(BaseModel):
    name: str = Field(min_length=1)
    price: int

class CreateCoffeeResponse(BaseModel):
    id: str
    name: str
    price: int

class RegisterMemberRequest(BaseModel):
    memberId: str
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)

class RegisterMemberResponse(BaseModel):
    memberId: str
    name: str
    phone: str
    points: int

class PurchaseRequest(BaseModel):
    memberId: str
    coffeeId: str
    quantity: int

class PurchaseResponse(BaseModel):
    purchaseId: str
    memberId: str
    coffeeId: str
    quantity: int
    totalAmount: int
    pointsEarned: int
    totalPoints: int


class RedeemRequest(BaseModel):
    pointsToUse: int
    price: int

class RedeemResponse(BaseModel):
    memberId: str
    usedPoints: int
    discountAmount: int
    discountedPrice: int
    remainingPoints: int


@app.post("/coffees", response_model=CreateCoffeeResponse)
def create_coffee(req: CreateCoffeeRequest) -> CreateCoffeeResponse:
    if req.price <= 0:
        raise HTTPException(status_code=400, detail="price must be a positive integer")

    pool = _require_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(
                    "INSERT INTO coffee (name, price) VALUES (%s, %s) RETURNING \"coffeeId\", name, price;",
                    (req.name, Decimal(req.price)),
                )
            except IntegrityError:
                conn.rollback()
                raise HTTPException(status_code=400, detail="Coffee name must be unique")

            row = cur.fetchone()
            conn.commit()
            return CreateCoffeeResponse(
                id=str(row["coffeeId"]),
                name=row["name"],
                price=int(Decimal(row["price"])),
            )
    finally:
        pool.putconn(conn)


@app.post("/members", response_model=RegisterMemberResponse)
def register_member(req: RegisterMemberRequest) -> RegisterMemberResponse:
    member_id = _parse_positive_int(req.memberId, "memberId")
    pool = _require_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(
                    'INSERT INTO member ("memberId", name, phone) VALUES (%s, %s, %s) RETURNING "memberId", name, phone, points;',
                    (member_id, req.name, req.phone),
                )
            except IntegrityError:
                conn.rollback()
                raise HTTPException(status_code=400, detail="memberId and phone must be unique")

            row = cur.fetchone()
            conn.commit()
            return RegisterMemberResponse(
                memberId=str(row["memberId"]),
                name=row["name"],
                phone=row["phone"],
                points=int(row["points"]),
            )
    finally:
        pool.putconn(conn)


@app.post("/purchase", response_model=PurchaseResponse)
def purchase(req: PurchaseRequest) -> PurchaseResponse:
    member_id = _parse_positive_int(req.memberId, "memberId")
    quantity = _parse_positive_int(req.quantity, "quantity")
    coffee_id = req.coffeeId

    pool = _require_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Lock member row to make points updates safe.
            cur.execute('SELECT "memberId", points FROM member WHERE "memberId" = %s FOR UPDATE;', (member_id,))
            member_row = cur.fetchone()
            if member_row is None:
                conn.rollback()
                raise HTTPException(status_code=404, detail="memberId not found")

            cur.execute('SELECT "coffeeId", price FROM coffee WHERE "coffeeId" = %s;', (coffee_id,))
            coffee_row = cur.fetchone()
            if coffee_row is None:
                conn.rollback()
                raise HTTPException(status_code=404, detail="coffeeId not found")

            price = Decimal(coffee_row["price"])
            total_amount = price * Decimal(quantity)
            total_amount_int = int(total_amount)
            points_earned = int(total_amount_int // 50)
            new_points = int(member_row["points"]) + points_earned

            cur.execute('UPDATE member SET points = %s WHERE "memberId" = %s;', (new_points, member_id))
            cur.execute(
                'INSERT INTO purchase_history ("memberId", "coffeeId", quantity, "totalAmount", "pointsEarned", "totalPoints") '
                'VALUES (%s, %s, %s, %s, %s, %s) RETURNING "purchaseId";',
                (member_id, coffee_id, quantity, total_amount, points_earned, new_points),
            )
            purchase_row = cur.fetchone()
            conn.commit()
            return PurchaseResponse(
                purchaseId=str(purchase_row["purchaseId"]),
                memberId=str(member_id),
                coffeeId=str(coffee_id),
                quantity=quantity,
                totalAmount=total_amount_int,
                pointsEarned=points_earned,
                totalPoints=new_points,
            )
    finally:
        pool.putconn(conn)


@app.post("/members/{memberId}/redeem", response_model=RedeemResponse)
def redeem(memberId: str, req: RedeemRequest) -> RedeemResponse:
    member_id = _parse_positive_int(memberId, "memberId")
    points_to_use = _parse_non_negative_int(req.pointsToUse, "pointsToUse")
    price = _parse_positive_int(req.price, "price")

    pool = _require_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT "memberId", points FROM member WHERE "memberId" = %s FOR UPDATE;', (member_id,))
            member_row = cur.fetchone()
            if member_row is None:
                conn.rollback()
                raise HTTPException(status_code=404, detail="memberId not found")

            current_points = int(member_row["points"])
            if points_to_use > current_points:
                conn.rollback()
                raise HTTPException(status_code=400, detail="pointsToUse must be <= available points")

            if points_to_use > price:
                conn.rollback()
                raise HTTPException(status_code=400, detail="pointsToUse must be <= price")
                
            discount_amount = points_to_use
            discounted_price = price - discount_amount
            remaining_points = current_points - points_to_use

            cur.execute('UPDATE member SET points = %s WHERE "memberId" = %s;', (remaining_points, member_id))
            cur.execute(
                'INSERT INTO redeem_history (member_id, coffee_id, points_redeemed) VALUES (%s, %s, %s);',
                (member_id, REDEMPTION_COFFEE_ID, points_to_use),
            )
            conn.commit()
            return RedeemResponse(
                memberId=str(member_id),
                usedPoints=points_to_use,
                discountAmount=discount_amount,
                discountedPrice=discounted_price,
                remainingPoints=remaining_points,
            )
    finally:
        pool.putconn(conn)
