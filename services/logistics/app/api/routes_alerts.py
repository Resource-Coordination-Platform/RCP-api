from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.database import get_db
from app.api.dependencies import get_principal, require_roles
from app.core.auth import Principal
from app.events.publisher import emit
from app.models.alert import DisasterAlert
from app.schemas.alert_schema import DisasterAlertCreate, DisasterAlertRead

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.post("", response_model=DisasterAlertRead, status_code=status.HTTP_201_CREATED)
def create_alert(
    data: DisasterAlertCreate,
    db: Session = Depends(get_db),
    # principal for required roles
    principal: Principal = Depends(require_roles("tenant_admin", "coordinator")),
):
    # Admin need an tenant id
    if not principal.tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID missing in token")
        
    new_alert = DisasterAlert(
        tenant_id=principal.tenant_id,  
        title=data.title,
        message=data.message,
        severity=data.severity,
        created_by=principal.user_id    
    )
    
    db.add(new_alert)
    db.flush()
    # server_default(func.now()) values aren't loaded after flush —
    # refresh fetches the DB-generated created_at for the emit payload.
    db.refresh(new_alert)

    from datetime import datetime, timezone
    import logging
    _log = logging.getLogger(__name__)

    ts = (
        new_alert.created_at.isoformat()
        if new_alert.created_at
        else datetime.now(timezone.utc).isoformat()
    )

    _log.info(
        "Emitting logistics.alert.created for alert %s (tenant=%s)",
        new_alert.id, principal.tenant_id,
    )

    # RabbitMQ outbox event → RTO consumer → WebSocket broadcast
    emit(
        db,
        routing_key="logistics.alert.created",
        tenant_id=principal.tenant_id,
        data={
            "alert_id": str(new_alert.id),
            "tenant_id": str(principal.tenant_id),
            "title": new_alert.title,
            "message": new_alert.message,
            "severity": new_alert.severity.value,
            "created_by": str(new_alert.created_by),
            "created_at": ts,
        },
    )

    db.commit()
    db.refresh(new_alert)
    return new_alert


# 2. For the victim to receive alerts relevant to their area (this refers to the 'Alerts' tab in the app).
@router.get("", response_model=list[DisasterAlertRead])
def get_alerts(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal), # anyone can access this route who logged
):
    # send empty lost if tenant id missing
    if not principal.tenant_id:
        return []
        
    # query is filtering for only select principal tenant id matching alerts
    query = select(DisasterAlert).where(
        DisasterAlert.tenant_id == principal.tenant_id
    ).order_by(DisasterAlert.created_at.desc())
    
    alerts = db.scalars(query).all()
    return list(alerts)