from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_and_ready() -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_register_login_and_me() -> None:
    registered = client.post(
        "/api/auth/register",
        json={"name": "Ada", "email": "ada@example.com", "password": "password1"},
    )
    assert registered.status_code == 201
    token = registered.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"
    assert me.json()["name"] == "Ada"

    logged_in = client.post(
        "/api/auth/login",
        json={"email": "ada@example.com", "password": "password1"},
    )
    assert logged_in.status_code == 200


def test_duplicate_email_and_bad_password() -> None:
    body = {"name": "Ada", "email": "ada@example.com", "password": "password1"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/register", json=body).status_code == 409
    bad = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "nope-nope"})
    assert bad.status_code == 401


def test_refresh_rotates_and_reuse_fails() -> None:
    client.post(
        "/api/auth/register",
        json={"name": "Ada", "email": "ada@example.com", "password": "password1"},
    )
    first = client.cookies.get("refresh_token")
    refreshed = client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    assert client.cookies.get("refresh_token") != first

    reused = client.post("/api/auth/refresh", cookies={"refresh_token": first})
    assert reused.status_code == 401


def test_logout_revokes_refresh() -> None:
    client.post(
        "/api/auth/register",
        json={"name": "Ada", "email": "ada@example.com", "password": "password1"},
    )
    assert client.post("/api/auth/logout").status_code == 204
    assert client.post("/api/auth/refresh").status_code == 401


def test_lookup_user_by_email() -> None:
    registered = client.post(
        "/api/auth/register",
        json={"name": "Ada", "email": "ada@example.com", "password": "password1"},
    )
    token = registered.json()["access_token"]
    found = client.get(
        "/api/auth/users",
        params={"email": "ada@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert found.status_code == 200
    assert found.json()["name"] == "Ada"
    missing = client.get(
        "/api/auth/users",
        params={"email": "missing@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing.status_code == 404
