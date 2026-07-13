"""Volunteer profile endpoints — mobile app, VOLUNTEER actors only.

The profile row itself is created by the IAM event consumer when the
user registers; these endpoints let the volunteer complete and maintain
the operational half (district, city, skills, availability).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from rcp_common.auth import Principal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.database import get_db
from app.models import VolunteerProfile
from app.schemas.volunteer_schema import (
    AvailabilityUpdate,
    VolunteerProfileRead,
    VolunteerProfileUpdate,
)

router = APIRouter(prefix="/api/volunteer/profiles", tags=["volunteer-profiles"])


def _own_profile(db: Session, principal: Principal) -> VolunteerProfile:
    profile = db.scalars(
        select(VolunteerProfile).where(VolunteerProfile.user_id == principal.user_id)
    ).first()
    if profile is None:
        # registration event still in flight — ask the app to retry
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Profile not provisioned yet; retry shortly",
        )
    return profile


@router.get("/me", response_model=VolunteerProfileRead)
def read_my_profile(
    principal: Principal = Depends(require_roles("volunteer")),
    db: Session = Depends(get_db),
):
    return _own_profile(db, principal)


@router.put("/me", response_model=VolunteerProfileRead)
def update_my_profile(
    data: VolunteerProfileUpdate,
    principal: Principal = Depends(require_roles("volunteer")),
    db: Session = Depends(get_db),
):
    profile = _own_profile(db, principal)
    profile.base_district = data.base_district
    profile.city = data.city
    profile.available_status = data.available_status
    profile.skills = data.skills
    db.commit()
    db.refresh(profile)
    return profile


@router.patch("/me/availability", response_model=VolunteerProfileRead)
def set_availability(
    data: AvailabilityUpdate,
    principal: Principal = Depends(require_roles("volunteer")),
    db: Session = Depends(get_db),
):
    profile = _own_profile(db, principal)
    if data.available_status and profile.base_district is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Set base_district before going available",
        )
    profile.available_status = data.available_status
    db.commit()
    db.refresh(profile)
    return profile
