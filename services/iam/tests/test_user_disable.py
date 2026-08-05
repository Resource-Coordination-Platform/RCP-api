import uuid
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from app.models import User, UserType, RefreshToken
from app.schemas.auth_schema import LoginRequest
from app.services import admin as admin_service
from app.services import auth as auth_service
from app.api import routes_auth

def test_login_disabled_user_raises_value_error():
    mock_db = MagicMock()
    mock_user = MagicMock(spec=User)
    mock_user.is_active = False
    
    mock_db.scalars.return_value.first.return_value = mock_user

    with patch("app.services.auth.verify_password", return_value=True):
        with pytest.raises(ValueError) as exc_info:
            auth_service.login(mock_db, LoginRequest(email="test@example.com", password="password"))
    
        assert str(exc_info.value) == "USER_DISABLED"

def test_login_route_disabled_user_returns_403():
    mock_db = MagicMock()
    with patch("app.services.auth.login", side_effect=ValueError("USER_DISABLED")):
        with pytest.raises(HTTPException) as exc_info:
            routes_auth.login(LoginRequest(email="test@example.com", password="password"), db=mock_db)
        
        assert exc_info.value.status_code == 403
        assert "disabled or banned" in exc_info.value.detail

def test_set_user_status_disabled_revokes_refresh_tokens():
    mock_db = MagicMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid.uuid4()
    mock_user.tenant_id = None
    mock_user.user_type = UserType.VOLUNTEER
    mock_user.email = "volunteer@example.com"
    mock_user.full_name = "Jane Volunteer"
    mock_user.phone = "123456"
    mock_user.roles = ["volunteer"]
    mock_user.is_active = False

    mock_db.scalars.return_value.first.return_value = mock_user

    updated_user = admin_service.set_user_status(mock_db, mock_user.id, "disabled")

    assert updated_user.status == "disabled"
    # Verify db.query(RefreshToken) was called to revoke tokens
    mock_db.query.assert_called_with(RefreshToken)
