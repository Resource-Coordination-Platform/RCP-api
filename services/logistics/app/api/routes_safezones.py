from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.database import get_db
from app.api.dependencies import get_principal, require_roles
from app.core.auth import Principal
from app.events.publisher import emit
from app.models.safezones import SafeZone
from app.schemas.safe_zones_schema import SafeZoneCreate, SafeZoneRead

router = APIRouter(prefix="/api/safe-zones", tags=["safe-zones"])



@router.post("", response_model=SafeZoneRead, status_code=status.HTTP_201_CREATED)
def create_safe_zone(
    data: SafeZoneCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("tenant_admin", "coordinator")),
):
    if not principal.tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID missing in token")
        
    new_safezone = SafeZone(
        tenant_id=principal.tenant_id,  
        name=data.name,
        lat=data.lat,
        lng=data.lng,
        type=data.type,
        created_by=principal.user_id    
    )
    
    db.add(new_safezone)
    db.flush()
    db.refresh(new_safezone)

    # in future if we need to add that we crteated a new safezone to a another service just add below code :)))
    # emit(principal.tenant_id, "safezone.created", str(new_safezone.id), payload=data.model_dump())

    return new_safezone

#for victim see locations
@router.get("", response_model=list[SafeZoneRead])
def get_safe_zones(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal), 
):
    if not principal.tenant_id:
        return []
        
    #so only get records that own by relavant tenant
    query = select(SafeZone).where(
        SafeZone.tenant_id == principal.tenant_id
    ).order_by(SafeZone.created_at.desc())
    
    safe_zones = db.scalars(query).all()
    
    return list(safe_zones)