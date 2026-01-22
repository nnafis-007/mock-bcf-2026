# Database Schema (matches `tables.md`)

## 1. member

**Columns**

- `memberId` (PK)
- `name`: text
- `phone`: text
- `points` (num): numeric points value

## 2. coffee

**Columns**

- `coffeeId` (PK): generated UUID
- `name`: text
- `price`: numeric

## 3. Purchase_history

**Columns**

- `purchaseId` (PK): generated integer ID
- `memberId` (FK → member.memberId)
- `coffeeId` (FK → coffee.coffeeId)
- `quantity`: integer
- `totalAmount`: numeric
- `pointsEarned`: integer
- `totalPoints`: integer

## 4. Redeem_history

**Columns**

- `redeem_id` (PK + UUID): generated UUID
- `member_id` (FK → member.memberId)
- `coffee_id` (FK → coffee.coffeeId)
- `points_redeemed`: integer
- `redeemed_at` (generated): timestamp
