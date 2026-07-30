#meke thiyenne bn ara routes_payements wala endpoint ekedi use una request saha reponse wala data thiyena type gana

import uuid
from pydantic import BaseModel

class PaymentCheckoutRequest(BaseModel):
    tenant_id: uuid.UUID   # <--- මේක අලුතින් දාන්න
    category_id: uuid.UUID
    amount: float
    quantity: int

class PaymentCheckoutResponse(BaseModel):
    order_id: str
    merchant_id: str
    hash: str
    amount: float
    currency: str
    items: str       