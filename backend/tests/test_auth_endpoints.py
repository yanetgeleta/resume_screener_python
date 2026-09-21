import pytest
from rest_framework import status
from rest_framework.test import APIClient

@pytest.mark.django_db
def test_company_registration_and_login_flow():
    client = APIClient()

    # 1. Test OPTIONS preflight on /api/auth/register/ does not reject with 401
    options_resp = client.options("/api/auth/register/")
    assert options_resp.status_code == status.HTTP_200_OK

    # 2. Test registration with email, company_name, password
    register_payload = {
        "email": "test-recruiter@company.com",
        "company_name": "Acme Talent",
        "password": "StrongPassword123!",
    }
    register_resp = client.post("/api/auth/register/", data=register_payload, format="json")
    assert register_resp.status_code == status.HTTP_201_CREATED
    assert register_resp.data["email"] == "test-recruiter@company.com"
    assert register_resp.data["company_name"] == "Acme Talent"
    assert "password" not in register_resp.data

    # 3. Test login with registered credentials
    login_payload = {
        "email": "test-recruiter@company.com",
        "password": "StrongPassword123!",
    }
    login_resp = client.post("/api/auth/login/", data=login_payload, format="json")
    assert login_resp.status_code == status.HTTP_200_OK
    assert "access" in login_resp.data
    assert "refresh" in login_resp.data

    # 4. Test token refresh with refresh token
    refresh_payload = {
        "refresh": login_resp.data["refresh"]
    }
    refresh_resp = client.post("/api/auth/refresh/", data=refresh_payload, format="json")
    assert refresh_resp.status_code == status.HTTP_200_OK
    assert "access" in refresh_resp.data
