BEGIN;

-- Needed for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DROP TABLE IF EXISTS redeem_history;
DROP TABLE IF EXISTS purchase_history;
DROP TABLE IF EXISTS coffee;
DROP TABLE IF EXISTS member;

-- 1. member -> memberId(PK), name, phone, points(num)
CREATE TABLE member (
    "memberId" BIGSERIAL PRIMARY KEY,
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
    "purchaseId" BIGSERIAL PRIMARY KEY DEFAULT gen_random_uuid(),
    "memberId" BIGINT NOT NULL REFERENCES member("memberId"),
    "coffeeId" UUID NOT NULL REFERENCES coffee("coffeeId"),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    "totalAmount" NUMERIC(10, 2) NOT NULL,
    "pointsEarned" INTEGER NOT NULL,
    "totalPoints" INTEGER NOT NULL
);

-- 4. Redeem_history -> redeem_id(PK + UUID), member_id(FK), coffee_id(FK), points_redeemed, redeemed_at(generated)
CREATE TABLE redeem_history (
    redeem_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id BIGINT NOT NULL REFERENCES member("memberId"),
    coffee_id UUID NOT NULL REFERENCES coffee("coffeeId"),
    points_redeemed INTEGER NOT NULL CHECK (points_redeemed >= 0),
    redeemed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Sentinel coffee row used for point redemptions (API doesn't provide coffeeId).
-- Keeps schema shape intact while satisfying redeem_history.coffee_id NOT NULL.
-- INSERT INTO coffee ("coffeeId", name, price)
-- VALUES ('00000000-0000-0000-0000-000000000000', '__REDEMPTION__', 1)
-- ON CONFLICT (name) DO NOTHING;

COMMIT;
