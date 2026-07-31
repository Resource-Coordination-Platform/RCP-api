# volunteer/app/api/routes_reports.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from rcp_common.auth import Principal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.database import get_db
from app.models import VolunteerProfile
from app.models.report import VolunteerReport
from app.schemas.report_schema import VolunteerReportCreate, VolunteerReportRead

router = APIRouter(prefix="/api/volunteer/reports", tags=["volunteer-reports"])

# Volunteer කෙනෙක්ට විතරක් මේකට එන්න පුළුවන් වෙන්න හදන්නේ
_volunteer = require_roles("volunteer")

@router.post("", response_model=VolunteerReportRead, status_code=status.HTTP_201_CREATED)
def submit_report(
    data: VolunteerReportCreate,
    principal: Principal = Depends(_volunteer),
    db: Session = Depends(get_db),
):
    # මුලින්ම ලොග් වෙලා ඉන්න Volunteer ගේ Profile එක හොයාගන්නවා
    profile = db.scalars(
        select(VolunteerProfile).where(VolunteerProfile.user_id == principal.user_id)
    ).first()
    
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Volunteer profile not found")

    # අලුත් රිපෝට් එක DB එකට සේව් කරනවා
    new_report = VolunteerReport(
        volunteer_id=profile.id,
        category=data.category,
        severity=data.severity,
        district=data.district,
        city=data.city,
        description=data.description,
        image_url=data.image_url,
        status="PENDING"
    )
    
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    
    return new_report