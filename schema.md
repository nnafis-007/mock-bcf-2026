# Database Schema Documentation (Coffee Loyalty API)

Target DB: **PostgreSQL**

This schema supports these API flows:
- Create coffee items (`POST /coffees`)
- Register members (`POST /members`)
- Record purchases and earn points (`POST /purchase`)
- Redeem points for discount (`POST /members/{memberId}/redeem`)

> Notes
> - IDs are stored as UUIDs (you can generate them in the app, or in Postgres via `gen_random_uuid()`).
> - Points in your examples match: **1 point per 50 Tk spent**, i.e. `points_earned = floor(total_amount / 50)`.
> - Discount in your example is **1 Tk per point**, i.e. `discount_amount = points_used`.

---

## Entity Relationship Overview

- **Member 1 ⟶ N Purchase** (a member can have many purchases)
- **Coffee 1 ⟶ N Purchase** (a coffee can appear in many purchases)
- **Member 1 ⟶ N Redemption** (a member can redeem points many times)

Purchases and redemptions form a “ledger” of point changes; `members.points_balance` is stored as a **denormalized** current balance for fast reads.

---

## Table: `members`

Stores member identity and their current points balance.

| Column | Type | Null | Key | Default | Description |
|---|---|---:|---|---|---|
| `member_id` | `uuid` | NO | PK | `gen_random_uuid()` | Member identifier used by the API (`memberId`). |
| `name` | `text` | NO |  |  | Member name. |
| `phone` | `text` | NO | UNIQUE |  | Phone number. Enforce uniqueness to prevent duplicate registrations. |
| `points_balance` | `integer` | NO |  | `0` | Current points available for redemption. Must be maintained by app logic or triggers. |
| `created_at` | `timestamptz` | NO |  | `now()` | Creation timestamp. |
| `updated_at` | `timestamptz` | NO |  | `now()` | Last update timestamp (optional; can be maintained via trigger). |

**Primary Key**
- `members(member_id)`

**Unique Constraints**
- `members(phone)`

**Relationships**
- Referenced by `purchases.member_id` (FK)
- Referenced by `redemptions.member_id` (FK)

**Recommended Checks**
- `points_balance >= 0`

**Recommended Indexes**
- Unique index on `phone` (provided by UNIQUE)

---

## Table: `coffees`

Stores coffee catalog items.

| Column | Type | Null | Key | Default | Description |
|---|---|---:|---|---|---|
| `coffee_id` | `uuid` | NO | PK | `gen_random_uuid()` | Coffee identifier used by the API (`coffeeId`). |
| `name` | `text` | NO | UNIQUE |  | Coffee name (e.g., Espresso). |
| `price` | `integer` | NO |  |  | Price in Tk (integer) as shown in your API examples. |
| `is_active` | `boolean` | NO |  | `true` | Whether the item is available for purchase (optional but useful). |
| `created_at` | `timestamptz` | NO |  | `now()` | Creation timestamp. |
| `updated_at` | `timestamptz` | NO |  | `now()` | Last update timestamp (optional). |

**Primary Key**
- `coffees(coffee_id)`

**Unique Constraints**
- `coffees(name)`

**Relationships**
- Referenced by `purchases.coffee_id` (FK)

**Recommended Checks**
- `price >= 0`

---

## Table: `purchases`

Stores every purchase event (used to calculate/track earned points).

Why this table exists:
- Drives purchase history
- Stores a snapshot of pricing at the moment of purchase
- Stores points earned for auditability

| Column | Type | Null | Key | Default | Description |
|---|---|---:|---|---|---|
| `purchase_id` | `uuid` | NO | PK | `gen_random_uuid()` | Purchase identifier.
| `member_id` | `uuid` | NO | FK |  | Member making the purchase.
| `coffee_id` | `uuid` | NO | FK |  | Coffee item purchased.
| `quantity` | `integer` | NO |  |  | Quantity purchased.
| `unit_price` | `integer` | NO |  |  | Price-per-item at time of purchase (snapshot from `coffees.price`).
| `total_amount` | `integer` | NO |  |  | `quantity * unit_price` (can be computed in app or generated column).
| `points_earned` | `integer` | NO |  |  | Points earned for this purchase, e.g. `floor(total_amount/50)`.
| `created_at` | `timestamptz` | NO |  | `now()` | Purchase timestamp.

**Primary Key**
- `purchases(purchase_id)`

**Foreign Keys**
- `purchases(member_id)` → `members(member_id)`
- `purchases(coffee_id)` → `coffees(coffee_id)`

**Relationships**
- Many purchases belong to one member
- Many purchases belong to one coffee

**Recommended Checks**
- `quantity > 0`
- `unit_price >= 0`
- `total_amount = quantity * unit_price` (enforce via generated column or trigger)
- `points_earned >= 0`

**Recommended Indexes**
- Index on `member_id` (query member purchase history)
- Index on `coffee_id` (analytics)
- Optional composite index on `(member_id, created_at)`

---

## Table: `redemptions`

Stores each redemption of points (discount events).

Why this table exists:
- Audit trail for discounts
- Enables reconstructing points balance if needed

| Column | Type | Null | Key | Default | Description |
|---|---|---:|---|---|---|
| `redemption_id` | `uuid` | NO | PK | `gen_random_uuid()` | Redemption identifier.
| `member_id` | `uuid` | NO | FK |  | Member redeeming points.
| `points_used` | `integer` | NO |  |  | Points the member chose to redeem.
| `discount_amount` | `integer` | NO |  |  | Discount in Tk. In your example: `discount_amount = points_used`.
| `original_price` | `integer` | NO |  |  | Price before discount (from request body `price`).
| `final_price` | `integer` | NO |  |  | `original_price - discount_amount` (should not go below 0).
| `created_at` | `timestamptz` | NO |  | `now()` | Redemption timestamp.

**Primary Key**
- `redemptions(redemption_id)`

**Foreign Keys**
- `redemptions(member_id)` → `members(member_id)`

**Recommended Checks**
- `points_used > 0`
- `discount_amount >= 0`
- `original_price >= 0`
- `final_price >= 0`
- `final_price = original_price - discount_amount` (generated column or trigger)

**Business Rule (Enforced in App or Trigger)**
- `points_used <= members.points_balance` at time of redemption

**Recommended Indexes**
- Index on `member_id`
- Optional composite index on `(member_id, created_at)`

---

## How Points Are Maintained

There are two common approaches:

1) **Denormalized balance + ledger tables (recommended)**
- Source of truth: `purchases` and `redemptions`
- Fast reads: `members.points_balance`
- Maintenance: update `members.points_balance` when inserting into `purchases` (add) and `redemptions` (subtract)

2) **Ledger only (no stored balance)**
- Remove `members.points_balance`
- Compute balance as:

$$\text{points_balance} = \sum(\text{purchases.points_earned}) - \sum(\text{redemptions.points_used})$$

Approach (1) matches your API needs (validate redemption quickly) while still keeping an audit trail.

---

## Summary of Keys & Relationships

- `members.member_id` (PK)
- `coffees.coffee_id` (PK)
- `purchases.purchase_id` (PK)
  - `purchases.member_id` → `members.member_id` (FK)
  - `purchases.coffee_id` → `coffees.coffee_id` (FK)
- `redemptions.redemption_id` (PK)
  - `redemptions.member_id` → `members.member_id` (FK)
