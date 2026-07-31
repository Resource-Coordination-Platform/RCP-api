from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.auth import Principal
from app.db.database import get_db
from app.schemas.payment_schema import PaymentCheckoutRequest, PaymentCheckoutResponse
from app.services import payment as payment_service

router = APIRouter(prefix="/api/payments", tags=["payments"])

@router.post("/checkout", response_model=PaymentCheckoutResponse)
def create_checkout(
    data: PaymentCheckoutRequest,
    db: Session = Depends(get_db),
    # Volunteer ට විතරයි සල්ලි ගෙවන්න පුළුවන්
    principal: Principal = Depends(require_roles("volunteer")),
):
    """App එකෙන් PayHere එකට යන්න ඕනේ කරන Hash එක හදලා දෙනවා"""
    return payment_service.create_checkout_session(db, data.tenant_id, principal.user_id, data)