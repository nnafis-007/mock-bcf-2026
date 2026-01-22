import pytest
import requests
import uuid

BASE_URL = "http://localhost:8000"

# ----------------------
# Helper Functions
# ----------------------

def random_coffee_payload():
    return {
        "name": f"test_Coffee_{uuid.uuid4().hex[:6]}",
        "price": 100  # positive integer
    }

def random_member_payload():
    return {
        "memberId": f"test_member_{uuid.uuid4().hex[:6]}",
        "name": f"test_Member_{uuid.uuid4().hex[:6]}",
        "phone": f"01{uuid.uuid4().int % 100000000:08d}"
    }

def create_coffee(payload):
    return requests.post(BASE_URL + "/coffees", json=payload)

def create_member(payload):
    return requests.post(BASE_URL + "/members", json=payload)

def purchase_coffee(payload):
    return requests.post(BASE_URL + "/purchase", json=payload)

def redeem_points(member_id, payload):
    return requests.post(BASE_URL + f"/members/{member_id}/redeem", json=payload)

# ----------------------
# Tests
# ----------------------

def test_api_health():
    response = requests.get(BASE_URL)
    assert response.status_code == 200

# ----------------------
# Coffee Tests
# ----------------------

def test_create_coffee():
    payload = random_coffee_payload()
    response = create_coffee(payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["price"] == payload["price"]
    assert "id" in data

# ----------------------
# Member Tests
# ----------------------

def test_create_member():
    payload = random_member_payload()
    response = create_member(payload)
    print(response.text)
    assert response.status_code == 200
    data = response.json()
    assert data["memberId"] == payload["memberId"]
    assert data["name"] == payload["name"]
    assert data["phone"] == payload["phone"]
    assert data["points"] >= 0

# ----------------------
# Purchase Tests
# ----------------------

def test_purchase_coffee():
    # create coffee and member first
    coffee = create_coffee(random_coffee_payload()).json()
    member = create_member(random_member_payload()).json()

    payload = {
        "memberId": member["memberId"],
        "coffeeId": coffee["id"],
        "quantity": 3
    }

    response = purchase_coffee(payload)
    print(response.text)
    assert response.status_code == 200
    data = response.json()
    assert data["memberId"] == member["memberId"]
    assert data["coffeeId"] == coffee["id"]
    assert data["quantity"] == payload["quantity"]
    assert data["totalAmount"] == coffee["price"] * payload["quantity"]
    # points earned = floor(totalAmount / 50)
    assert data["pointsEarned"] == (coffee["price"] * payload["quantity"]) // 50
    assert data["totalPoints"] == data["pointsEarned"]

# ----------------------
# Redeem Points Tests
# ----------------------

def test_redeem_points():
    # create coffee and member
    coffee = create_coffee(random_coffee_payload()).json()
    member_payload = random_member_payload()
    member_payload["points"] = 200  # manually set points for testing redeem
    member = create_member(member_payload).json()

    # simulate purchase to earn points
    purchase_payload = {
        "memberId": member["memberId"],
        "coffeeId": coffee["id"],
        "quantity": 5
    }
    coffee_resp = purchase_coffee(purchase_payload).json()
    total_points = coffee_resp["totalPoints"]
    

    redeem_payload = {
        "pointsToUse": total_points - 1,
        "price": coffee["price"] + total_points + 1
    }

    response = redeem_points(member["memberId"], redeem_payload)
    print(response.text)
    assert response.status_code == 200
    data = response.json()
    assert data["memberId"] == member["memberId"]
    assert data["usedPoints"] == redeem_payload["pointsToUse"]
    assert data["discountedPrice"] == redeem_payload["price"] - data["discountAmount"]
    assert data["remainingPoints"] >= 0
