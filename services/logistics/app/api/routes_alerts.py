from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.database import get_db
from app.api.dependencies import get_principal, require_roles
from app.core.auth import Principal
from app.models.alert import DisasterAlert
from app.schemas.alert_schema import DisasterAlertCreate, DisasterAlertRead

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

# 1. Admin ට අලුත් Alert එකක් යවන්න (Dashboard එකෙන් කතා කරන්නේ මේකට)
@router.post("", response_model=DisasterAlertRead, status_code=status.HTTP_201_CREATED)
def create_alert(
    data: DisasterAlertCreate,
    db: Session = Depends(get_db),
    # Admin (හෝ Coordinator) අයට විතරයි මේක කරන්න පුළුවන්
    principal: Principal = Depends(require_roles("tenant_admin", "coordinator")),
):
    # Admin ට අනිවාර්යයෙන්ම Tenant ID එකක් තියෙන්න ඕනේ
    if not principal.tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID missing in token")
        
    new_alert = DisasterAlert(
        tenant_id=principal.tenant_id,  # Admin අයිති කඳවුරේ ID එක
        title=data.title,
        message=data.message,
        severity=data.severity,
        created_by=principal.user_id    # Alert එක හදපු Admin ගේ ID එක
    )
    
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)
    return new_alert


# 2. Victim ට තමන්ගේ ප්‍රදේශයට අදාළ Alerts ටික ගන්න (App එකේ Alerts Tab එකෙන් කතා කරන්නේ මේකට)
@router.get("", response_model=list[DisasterAlertRead])
def get_alerts(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal), # ලොග් වෙච්ච ඕනෑම කෙනෙක්ට පුළුවන්
):
    # Token එකේ Tenant ID එකක් නැත්නම් (තාම ලොකේෂන් සෙට් වෙලා නැත්නම්) හිස් ලිස්ට් එකක් යවනවා
    if not principal.tenant_id:
        return []
        
    # Victim ට අදාළ (Assigned) වෙලා තියෙන කඳවුරෙන් දාපු Alerts ටික විතරක් අලුත්ම එක උඩින් එන්න ෆිල්ටර් කරනවා
    query = select(DisasterAlert).where(
        DisasterAlert.tenant_id == principal.tenant_id
    ).order_by(DisasterAlert.created_at.desc())
    
    alerts = db.scalars(query).all()
    return list(alerts)