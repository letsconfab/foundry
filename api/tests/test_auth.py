"""
Tests for authentication endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import User


class TestAuthRegister:
    """Tests for POST /auth/register"""

    def test_register_success(self, client: TestClient):
        """Test successful user registration."""
        response = client.post("/auth/register", json={
            "name": "New User",
            "email": "newuser@example.com",
            "password": "securepassword123",
            "country": "US",
            "timezone": "America/New_York"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["name"] == "New User"
        assert "access_token" in data
        assert "id" in data

    def test_register_duplicate_email(self, client: TestClient, test_user: User):
        """Test registration with existing email fails."""
        response = client.post("/auth/register", json={
            "name": "Another User",
            "email": test_user.email,  # Same email as test_user
            "password": "password123",
            "country": "US",
            "timezone": "America/New_York"
        })
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    def test_register_invalid_email(self, client: TestClient):
        """Test registration with invalid email format."""
        response = client.post("/auth/register", json={
            "name": "User",
            "email": "not-an-email",
            "password": "password123",
            "country": "US",
            "timezone": "America/New_York"
        })
        assert response.status_code == 422  # Validation error


class TestAuthLogin:
    """Tests for POST /auth/login"""

    def test_login_success(self, client: TestClient, test_user: User):
        """Test successful login."""
        response = client.post("/auth/login", json={
            "email": test_user.email,
            "password": "testpassword"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["email"] == test_user.email

    def test_login_wrong_password(self, client: TestClient, test_user: User):
        """Test login with wrong password."""
        response = client.post("/auth/login", json={
            "email": test_user.email,
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with non-existent email."""
        response = client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "password123"
        })
        assert response.status_code == 401


class TestAuthMe:
    """Tests for GET /auth/me"""

    def test_get_current_user(self, client: TestClient, auth_headers: dict, test_user: User):
        """Test getting current user info."""
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["id"] == test_user.id

    def test_get_current_user_no_auth(self, client: TestClient):
        """Test accessing /auth/me without authentication."""
        response = client.get("/auth/me")
        # HTTPBearer returns 401 when no credentials provided, not 403
        assert response.status_code in [401, 403]

    def test_get_current_user_invalid_token(self, client: TestClient):
        """Test accessing /auth/me with invalid token."""
        response = client.get("/auth/me", headers={"Authorization": "Bearer invalid-token"})
        assert response.status_code == 401
