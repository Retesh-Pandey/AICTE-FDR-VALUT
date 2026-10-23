def test_unauthenticated_access_to_me(client):
    response = client.get("/me")
    assert response.status_code == 401
    assert "error" in response.json() or "detail" in response.json()

def test_invalid_token_access(client):
    response = client.get("/me", headers={"Authorization": "Bearer invalid.token.value"})
    assert response.status_code == 401

def test_institution_login_and_me(client):
    login_res = client.post("/auth/demo-login", json={"email": "institution@demo.test"})
    assert login_res.status_code == 200
    login_data = login_res.json()
    token = login_data["access_token"]
    assert login_data["user"]["role"] == "institution"

    me_res = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "institution@demo.test"
    assert me_data["role"] == "institution"
    assert me_data["institution"] is not None
    assert "Apex Institute of Technology" in me_data["institution"]["name"]

def test_role_enforcement_forbidden_for_institution(client):
    login_res = client.post("/auth/demo-login", json={"email": "institution@demo.test"})
    token = login_res.json()["access_token"]

    officer_res = client.get("/auth/officer-only", headers={"Authorization": f"Bearer {token}"})
    assert officer_res.status_code == 403
    assert officer_res.json().get("error", {}).get("code") == "FORBIDDEN_ROLE"

    admin_res = client.get("/auth/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert admin_res.status_code == 403
    assert admin_res.json().get("error", {}).get("code") == "FORBIDDEN_ROLE"

def test_officer_access(client):
    login_res = client.post("/auth/demo-login", json={"email": "officer@demo.test"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Officer can access officer-only
    officer_res = client.get("/auth/officer-only", headers={"Authorization": f"Bearer {token}"})
    assert officer_res.status_code == 200
    assert officer_res.json()["role"] == "officer"

    # Officer cannot access admin-only
    admin_res = client.get("/auth/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert admin_res.status_code == 403

def test_admin_access(client):
    login_res = client.post("/auth/demo-login", json={"email": "admin@demo.test"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Admin can access officer-only
    officer_res = client.get("/auth/officer-only", headers={"Authorization": f"Bearer {token}"})
    assert officer_res.status_code == 200

    # Admin can access admin-only
    admin_res = client.get("/auth/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert admin_res.status_code == 200
    assert admin_res.json()["role"] == "admin"
