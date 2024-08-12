from rave_python import Rave, RaveExceptions
from fastapi import HTTPException, status
from api.v1.models.payment import Payment
from sqlalchemy.orm import Session
from typing import Any, Optional
from decimal import Decimal
from decouple import config

from api.utils.settings import settings
from api.v1.models.payment import Payment
from api.v1.models import User, BillingPlan
from api.utils.db_validators import check_model_existence


class PaymentService:
    """Payment service functionality"""

    def create(self, db: Session, schema):
        """Create a new payment"""

        new_payment = Payment(**schema)
        db.add(new_payment)
        db.commit()
        db.refresh(new_payment)

        return new_payment

    def fetch_all(self, db: Session, **query_params: Optional[Any]):
        """Fetch all payments with option to search using query parameters"""

        query = db.query(Payment)

        # Enable filter by query parameter
        if query_params:
            for column, value in query_params.items():
                if hasattr(Payment, column) and value:
                    query = query.filter(getattr(Payment, column).ilike(f"%{value}%"))

        return query.all()

    def fetch(self, db: Session, payment_id: str):
        """Fetches a payment by id"""

        payment = check_model_existence(db, Payment, payment_id)
        return payment

    def get_payment_by_id(self, db: Session, payment_id: str):
        payment = check_model_existence(db, Payment, payment_id)
        return payment

    def get_payment_by_transaction_id(self, db: Session, transaction_id: str):
        try:
            payment = db.query(Payment).filter(Payment.transaction_id==transaction_id).first()
            return payment
        except Exception:
            raise HTTPException(status_code=404, detail='Payment record not found in the database')

    def fetch_by_user(self, db: Session, user_id, limit, page):
        """Fetches all payments of a user"""

        # check if user exists
        _ = check_model_existence(db, User, user_id)

        # calculating offset value
        # from page and limit given
        offset_value = (page - 1) * limit

        # Filter to return only payments of the user_id
        payments = (
            db.query(Payment)
            .filter(Payment.user_id == user_id)
            .offset(offset_value)
            .limit(limit)
            .all()
        )

        return payments

    def update(self, db: Session, payment_id: str, schema):
        """Updates a payment"""

        payment = self.fetch(db=db, payment_id=payment_id)

        # Update the fields with the provided schema data
        update_data = schema.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(payment, key, value)

        db.commit()
        db.refresh(payment)
        return payment

    def delete(self, db: Session, payment_id: str):
        """Deletes a payment"""

        payment = self.fetch(db=db, payment_id=payment_id)
        db.delete(payment)
        db.commit()


class PaymentGatewayService:
    """Payment gateway service functionality"""

    PAYMENT_GATEWAYS = ["Stripe", "Flutterwave", "Lemonsqueezy"]

    FLUTTERWAVE_ONE_OFF_PAY_URL = "https://checkout.flutterwave.com/v3/hosted/pay"

    def confirm_flutterwave_payment(self, user_id: str, data: dict, billing_plan: BillingPlan):
        """Handle checkout response from `flutterwave`"""
        if data.get('tx_ref') != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction reference error."
            )

        if data.get('status') not in ("successful", "completed"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction not successful."
            )

        if not data.get('transaction_id'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction id not found."
            )

        if config("PYTHON_ENV") in ["production", "prod"]:
            rave = Rave(
                settings.RAVE_PUBLIC_KEY, 
                settings.RAVE_SECRET_KEY, 
                production=True
            )
        else:
            rave = Rave(
                settings.RAVE_PUBLIC_KEY, 
                settings.RAVE_SECRET_KEY, 
                usingEnv=False
            )

        try:
            resp = rave.Account.verify(user_id)
        except RaveExceptions.TransactionVerificationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error: {e.err['errMsg']} [{e.err['flwRef']}]."
            )

        if resp.get('txRef') != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid response txn ref. If you were debited, contact you bank."
            )

        if resp.get('status') != "success":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No success response. If you were debited, contact you bank."
            )

        if not resp.get('transactionComplete') is True:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incomplete transaction. If you were debited, contact you bank."
            )

        if Decimal(resp.get('price')) != Decimal(f"{billing_plan.price}"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment amount. If you were debited, contact you bank."
            )
        
        if resp.get('currency') != billing_plan.currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid currency. If you were debited, contact you bank."
            )
        
        return True


payment_service = PaymentService()
payment_gateway_service = PaymentGatewayService()