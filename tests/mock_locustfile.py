from locust import HttpUser, task, between
import uuid
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------
# Helper Functions
# ----------------------

def random_coffee_payload():
    return {
        "name": f"Coffee_{uuid.uuid4().hex[:6]}",
        "price": random.randint(50, 500)  # positive integer
    }

def random_member_payload():
    return {
        "memberId": f"member_{uuid.uuid4().hex[:6]}",
        "name": f"Member_{uuid.uuid4().hex[:6]}",
        "phone": f"01{uuid.uuid4().int % 100000000:08d}"
    }

def create_coffee(client, payload):
    response = client.post("/coffees", json=payload)
    return response

def create_member(client, payload):
    response = client.post("/members", json=payload)
    return response

def purchase_coffee(client, payload):
    return client.post("/purchase", json=payload, catch_response=True)

def redeem_points(client, member_id, payload):
    return client.post(f"/members/{member_id}/redeem", json=payload, catch_response=True)

# ----------------------
# Normal Users
# ----------------------

class NormalUser(HttpUser):
    """
    Simulates typical coffee shop customers
    Weight: 70%
    """
    weight = 70
    wait_time = between(1, 3)

    @task(10)
    def buy_coffee(self):
        """Typical purchase flow"""
        # Create member and coffee
        member_response = create_member(self.client, random_member_payload())
        if member_response.status_code != 200:
            logger.error(f"Failed to create member: {member_response.status_code}")
            return
        
        coffee_response = create_coffee(self.client, random_coffee_payload())
        if coffee_response.status_code != 200:
            logger.error(f"Failed to create coffee: {coffee_response.status_code}")
            return
        
        try:
            member = member_response.json()
            coffee = coffee_response.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            return

        # Make purchase
        quantity = random.randint(1, 5)
        payload = {
            "memberId": member["memberId"],
            "coffeeId": coffee["id"],
            "quantity": quantity
        }
        with purchase_coffee(self.client, payload) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    # Validate points calculation
                    expected_points = (coffee["price"] * quantity) // 50
                    if data["pointsEarned"] != expected_points:
                        response.failure(f"Points mismatch: expected {expected_points}, got {data['pointsEarned']}")
                    else:
                        response.success()
                except Exception as e:
                    response.failure(f"Failed to parse response: {e}")
            else:
                response.failure(f"Purchase failed: {response.status_code}")

    @task(2)
    def redeem_member_points(self):
        """Redeem some points after purchase"""
        member_response = create_member(self.client, random_member_payload())
        if member_response.status_code != 200:
            logger.error(f"Failed to create member: {member_response.status_code}")
            return
        
        coffee_response = create_coffee(self.client, random_coffee_payload())
        if coffee_response.status_code != 200:
            logger.error(f"Failed to create coffee: {coffee_response.status_code}")
            return
        
        try:
            member = member_response.json()
            coffee = coffee_response.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            return

        # Simulate purchase to earn points
        quantity = 5
        purchase_payload = {
            "memberId": member["memberId"],
            "coffeeId": coffee["id"],
            "quantity": quantity
        }
        purchase_coffee(self.client, purchase_payload)

        # Redeem points
        points_to_use = 10
        redeem_payload = {
            "pointsToUse": points_to_use,
            "price": coffee["price"] * quantity
        }
        with redeem_points(self.client, member["memberId"], redeem_payload) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Redeem failed: {response.status_code}")

# ----------------------
# Edge Case Users
# ----------------------

class EdgeCaseUser(HttpUser):
    """
    Tests boundary conditions and invalid inputs
    Weight: 20%
    """
    weight = 20
    wait_time = between(2, 5)

    @task(5)
    def invalid_purchase(self):
        """Purchase with non-existent member or coffee"""
        payload = {
            "memberId": "invalid_member",
            "coffeeId": "invalid_coffee",
            "quantity": 1
        }
        response = purchase_coffee(self.client, payload)
        if response.status_code in [400, 404]:
            response.success()
        else:
            response.failure(f"Expected 400/404, got {response.status_code}")

    @task(3)
    def redeem_too_many_points(self):
        """Try to redeem more points than available"""
        member_response = create_member(self.client, random_member_payload())
        if member_response.status_code != 200:
            logger.error(f"Failed to create member: {member_response.status_code}")
            return
        
        try:
            member = member_response.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            return
        
        payload = {
            "pointsToUse": 1000,  # intentionally high
            "price": 500
        }
        with redeem_points(self.client, member["memberId"], payload) as response:
            if response.status_code == 400:
                response.success()
            else:
                response.failure(f"Expected 400 for excessive points, got {response.status_code}")

# ----------------------
# Stress Test Users
# ----------------------

class StressTestUser(HttpUser):
    """
    Aggressive user behavior for load testing
    Weight: 10%
    """
    weight = 10
    wait_time = between(0.1, 0.5)

    @task(10)
    def rapid_purchases(self):
        """Rapidly create purchases to stress the system"""
        member_response = create_member(self.client, random_member_payload())
        if member_response.status_code != 200:
            logger.error(f"Failed to create member: {member_response.status_code}")
            return
        
        coffee_response = create_coffee(self.client, random_coffee_payload())
        if coffee_response.status_code != 200:
            logger.error(f"Failed to create coffee: {coffee_response.status_code}")
            return
        
        try:
            member = member_response.json()
            coffee = coffee_response.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            return

        quantity = random.randint(1, 3)
        payload = {
            "memberId": member["memberId"],
            "coffeeId": coffee["id"],
            "quantity": quantity
        }
        with purchase_coffee(self.client, payload) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Rapid purchase failed: {response.status_code}")

    @task(5)
    def repeated_redeem(self):
        """Rapidly redeem points to test concurrency"""
        member_response = create_member(self.client, random_member_payload())
        if member_response.status_code != 200:
            logger.error(f"Failed to create member: {member_response.status_code}")
            return
        
        coffee_response = create_coffee(self.client, random_coffee_payload())
        if coffee_response.status_code != 200:
            logger.error(f"Failed to create coffee: {coffee_response.status_code}")
            return
        
        try:
            member = member_response.json()
            coffee = coffee_response.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            return

        purchase_payload = {
            "memberId": member["memberId"],
            "coffeeId": coffee["id"],
            "quantity": 5
        }
        purchase_coffee(self.client, purchase_payload)

        redeem_payload = {
            "pointsToUse": 5,
            "price": coffee["price"] * 5
        }
        with redeem_points(self.client, member["memberId"], redeem_payload) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Rapid redeem failed: {response.status_code}")