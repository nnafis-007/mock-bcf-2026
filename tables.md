1. member -> memberId(PK), name, phone, points(num)

2. Coffee -> coffeeId(generated + UUID + PK), name, price

3. Purchase_history -> purchaseId(generated+PK), memberId(FK), coffeeId(FK), quantity, totalAmount, pointsEarned, totalPoints

4. Redeem_history -> redeem_id(PK + UUID), member_id(FK), coffee_id(FK), points_redeemed, redeemed_at(generated)