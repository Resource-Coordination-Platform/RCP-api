import uuid
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from app.models import Tenant, User, UserType, RefreshToken
from app.schemas.auth_schema import LoginRequest
from app.services import admin as admin_service
from app.services import auth as auth_service
from app.api import routes_auth

def test_login_suspended_tenant_raises_value_error():
    mock_db = MagicMock()
    mock_tenant = MagicMock(spec=Tenant)
    mock_tenant.status = "suspended"
    
    mock_db.scalars.return_value.first.return_value = mock_tenant

    with pytest.raises(ValueError) as exc_info:
        auth_service.login(mock_db, LoginRequest(tenant_slug="test-tenant", email="admin@example.com", password="password"))

    assert str(exc_info.value) == "TENANT_SUSPENDED"

def test_login_route_suspended_tenant_returns_403():
    mock_db = MagicMock()
    with patch("app.services.auth.login", side_effect=ValueError("TENANT_SUSPENDED")):
        with pytest.raises(HTTPException) as exc_info:
            routes_auth.login(LoginRequest(tenant_slug="test-tenant", email="admin@example.com", password="password"), db=mock_db)
        
        assert exc_info.value.status_code == 403
        assert "tenant account has been suspended" in exc_info.value.detail

def test_set_tenant_status_suspended_revokes_tokens():
    mock_db = MagicMock()
    mock_tenant = MagicMock(spec=Tenant)
    mock_tenant.id = uuid.uuid4()
    mock_tenant.status = "suspended"

    mock_db.get.return_value = mock_tenant

    updated_tenant = admin_service.set_tenant_status(mock_db, mock_tenant.id, "suspended")

    assert updated_tenant.status == "suspended"
    mock_db.query.assert_called_with(RefreshToken)
