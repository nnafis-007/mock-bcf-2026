BEGIN;

-- Needed for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DROP TABLE IF EXISTS purchase_history;
DROP TABLE IF EXISTS coffee;
DROP TABLE IF EXISTS member;

-- 1. member -> memberId(PK), name, phone, points(num)
CREATE TABLE member (
    "memberId" TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT UNIQUE,
    points INTEGER NOT NULL DEFAULT 0
);

-- 2. Coffee -> coffeeId(generated + UUID + PK), name, price
CREATE TABLE coffee (
    "coffeeId" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    price NUMERIC(10, 2) NOT NULL CHECK (price > 0)
);

-- 3. Purchase_history -> purchaseId(generated+PK), memberId(FK), coffeeId(FK), quantity, totalAmount, pointsEarned, totalPoints
CREATE TABLE purchase_history (
    "purchaseId" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "memberId" TEXT NOT NULL REFERENCES member("memberId"),
    "coffeeId" UUID NOT NULL REFERENCES coffee("coffeeId"),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    "totalAmount" NUMERIC(10, 2) NOT NULL,
    "pointsEarned" INTEGER NOT NULL,
    "totalPoints" INTEGER NOT NULL
);

COMMIT;
