import pytest
from app.models import UserType

def test_register_user_api(client):
    """Test global user registration via the API."""
    payload = {
        "email": "api_test_user@example.com",
        "password": "strong_password123",
        "full_name": "API Test User",
        "phone": "0771234567",
        "user_type": "VOLUNTEER"
    }
    
    response = client.post("/api/auth/register", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "api_test_user@example.com"
    assert data["full_name"] == "API Test User"
    assert "id" in data

def test_register_duplicate_user_api(client):
    """Test that registering an existing email returns 409."""
    payload = {
        "email": "duplicate@example.com",
        "password": "password123",
        "full_name": "Dup User",
        "phone": "0770000000",
        "user_type": "VOLUNTEER"
    }
    
    # First registration
    client.post("/api/auth/register", json=payload)
    
    # Second registration should fail
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"

def test_login_api(client):
    """Test user login and token generation."""
    # First register a user
    payload = {
        "email": "login_test@example.com",
        "password": "login_password",
        "full_name": "Login User",
        "phone": "0771112222",
        "user_type": "VOLUNTEER"
    }
    client.post("/api/auth/register", json=payload)
    
    # Now login
    login_payload = {
        "email": "login_test@example.com",
        "password": "login_password"
    }
    response = client.post("/api/auth/login", json=login_payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

def test_get_profile_api(client):
    """Test fetching the logged-in user's profile."""
    # Register
    client.post("/api/auth/register", json={
        "email": "profile_test@example.com",
        "password": "profile_password",
        "full_name": "Profile User",
        "phone": "0773334444",
        "user_type": "VOLUNTEER"
    })
    
    # Login to get token
    login_response = client.post("/api/auth/login", json={
        "email": "profile_test@example.com",
        "password": "profile_password"
    })
    token = login_response.json()["access_token"]
    
    # Fetch profile using the Bearer token
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/auth/me", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "profile_test@example.com"
    assert data["full_name"] == "Profile User"
