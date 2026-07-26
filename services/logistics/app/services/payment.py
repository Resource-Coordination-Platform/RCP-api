import hashlib
import os
import uuid
from sqlalchemy.orm import Session
from app.models.payment_donation import PaymentDonation, PaymentStatus

# ඔයාගේ PayHere Merchant ID එකයි Secret එකයි මෙතනට දාන්න (දැනට Sandbox ඒවා)
PAYHERE_MERCHANT_ID = os.getenv("PAYHERE_MERCHANT_ID", "1236705") # ඔයාගේ ID එක දෙන්න
PAYHERE_SECRET = os.getenv("PAYHERE_SECRET", "MjgzMzI1Mzg5NTI5MTU4OTQwNjM2NDMyNDUxNzcyMjk1NDgwNzI3") # ඔයාගේ Secret එක දෙන්න

def generate_hash(order_id: str, amount: float, currency: str) -> str:
    """PayHere එක ඉල්ලන MD5 Hash කේතය හදන විදිහ"""
    merchant_secret_hash = hashlib.md5(PAYHERE_SECRET.encode('utf-8')).hexdigest().upper()
    amount_formatted = f"{amount:.2f}"
    hash_string = f"{PAYHERE_MERCHANT_ID}{order_id}{amount_formatted}{currency}{merchant_secret_hash}"
    return hashlib.md5(hash_string.encode('utf-8')).hexdigest().upper()

def create_checkout_session(db: Session, tenant_id: uuid.UUID, donor_user_id: uuid.UUID, data) -> dict:
    order_id = str(uuid.uuid4())
    
    # 1. මුලින්ම ගෙවීම "PENDING" විදිහට Database එකේ සේව් කරගන්නවා
    payment = PaymentDonation(
        tenant_id=tenant_id,
        donor_user_id=donor_user_id,
        category_id=data.category_id,
        amount=data.amount,
        currency="LKR",
        payhere_order_id=order_id,
        status=PaymentStatus.PENDING,
        quantity=data.quantity
    )
    db.add(payment)
    db.commit()

    # 2. Hash එක හදනවා
    payhere_hash = generate_hash(order_id, data.amount, "LKR")

    # 3. App එකට ඕනේ කරන දත්ත ටික යවනවා
    return {
        "order_id": order_id,
        "merchant_id": PAYHERE_MERCHANT_ID,
        "hash": payhere_hash,
        "amount": data.amount,
        "currency": "LKR",
        "items": "Disaster Relief Donation"
    }