import uuid
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from app.models import User, UserType
from app.schemas.auth_schema import ProfileUpdate, PasswordChange
from app.schemas.admin_schema import AdminPasswordReset
from app.services import auth as auth_service
from app.services import admin as admin_service

def test_update_user_profile():
    mock_db = MagicMock()
    mock_user = MagicMock(spec=User)
    mock_user.full_name = "Old Name"
    mock_user.phone = "000000"
    mock_user.tenant_id = None
    mock_user.user_type = UserType.VOLUNTEER
    mock_user.email = "test@example.com"
    mock_user.roles = ["volunteer"]

    mock_db.scalars.return_value.first.return_value = mock_user

    updated = auth_service.update_user_profile(
        mock_db, uuid.uuid4(), ProfileUpdate(full_name="New Name", phone="111111")
    )

    assert mock_user.full_name == "New Name"
    assert mock_user.phone == "111111"

def test_change_user_password_success():
    mock_db = MagicMock()
    mock_user = MagicMock(spec=User)
    mock_user.password_hash = "hashed_old"
    mock_user.id = uuid.uuid4()

    mock_db.scalars.return_value.first.return_value = mock_user

    with patch("app.services.auth.verify_password", return_value=True), \
         patch("app.services.auth.hash_password", return_value="hashed_new"):
        
        success = auth_service.change_user_password(
            mock_db, mock_user.id, PasswordChange(current_password="old_password_10", new_password="new_password_10")
        )
        assert success is True
        assert mock_user.password_hash == "hashed_new"

def test_change_user_password_invalid_current():
    mock_db = MagicMock()
    mock_user = MagicMock(spec=User)
    mock_user.password_hash = "hashed_old"
    mock_user.id = uuid.uuid4()

    mock_db.scalars.return_value.first.return_value = mock_user

    with patch("app.services.auth.verify_password", return_value=False):
        with pytest.raises(ValueError) as exc:
            auth_service.change_user_password(
                mock_db, mock_user.id, PasswordChange(current_password="wrong_password", new_password="new_password_10")
            )
        assert str(exc.value) == "INVALID_CURRENT_PASSWORD"

def test_admin_reset_user_password():
    mock_db = MagicMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid.uuid4()

    mock_db.scalars.return_value.first.return_value = mock_user

    with patch("app.services.admin.hash_password", return_value="hashed_temp"):
        res = admin_service.admin_reset_user_password(mock_db, mock_user.id, "temp_password_10")
        assert res.password_hash == "hashed_temp"
