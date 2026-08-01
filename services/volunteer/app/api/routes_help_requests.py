from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from rcp_common.auth import Principal

from app.api.dependencies import require_roles
from app.db.database import get_db
from app.models.victim_request import VictimRequest
from app.schemas.help_request_schema import VictimRequestCreate, VictimRequestRead

router = APIRouter(prefix="/api/volunteer/requests", tags=["victim-requests"])

_victim = require_roles("victim") # Victim ට විතරයි මේකට ඇතුළු විය හැක

# 1. Victim ට අලුතින් Request එකක් දාන්න (App එකෙන් කතා කරන්නේ මේකට)
@router.post("", response_model=VictimRequestRead, status_code=status.HTTP_201_CREATED)
def create_help_request(
    data: VictimRequestCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(_victim), # Victim ට විතරයි මේකට ඇතුළු විය හැක
):
    new_request = VictimRequest(
        victim_id=principal.user_id, # Token එකෙන් එන User ID එක
        disaster_type=data.disaster_type,
        needs=data.needs,
        description=data.description,
        latitude=data.latitude,
        longitude=data.longitude,
        status="PENDING"
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request


# 2. Admin ට තියෙන අලුත් Requests ටික බලන්න (Admin Dashboard එකෙන් කතා කරන්නේ මේකට)
@router.get("/pending", response_model=list[VictimRequestRead])
def get_pending_requests(
    db: Session = Depends(get_db),
    # Admin ලට විතරයි මේක බලන්න පුළුවන්
    principal: Principal = Depends(require_roles("tenant_admin", "coordinator", "super_admin")),
):
    query = select(VictimRequest).where(VictimRequest.status == "PENDING").order_by(VictimRequest.created_at.desc())
    requests = db.scalars(query).all()
    return list(requests)