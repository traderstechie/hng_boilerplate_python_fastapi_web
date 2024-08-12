from fastapi import Depends, APIRouter, status, Query, HTTPException, Request
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Annotated


from api.v1.services.payment import payment_service, payment_gateway_service as pg_service
from api.v1.services.billing_plan import billing_plan_service as bp_service
from api.v1.schemas.payment import PaymentListResponse, PaymentResponse
from api.utils.success_response import success_response
# from api.v1.services.payment import PaymentService
# from api.v1.models.billing_plan import BillingPlan
from api.v1.schemas.payment import PaymentCreate
from api.v1.services.user import user_service
from api.utils.settings import settings
from api.db.database import get_db
from api.v1.models import User


payment = APIRouter(prefix="/payments", tags=["Payments"])


@payment.get("/configure/{billing_plan_id}/{payment_gateway}", 
             status_code=status.HTTP_200_OK)
def configure_payment(
    billing_plan_id: str,
    payment_gateway: str,
    request: Request,
    current_user: User = Depends(user_service.get_current_user),
    db: Session = Depends(get_db)
):
    """
    This configures data for requests going to payment gateways
    """
    # CONFIRM payment_gateway
    if payment_gateway != "flutterwave":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Only fullterwave supported for now"
        )
    
    # GET billing plan
    bill_plan = bp_service.fetch(db, billing_plan_id)

    # CONFIGURE return url
    redirect_url = request.url_for(
        'handle_payment', billing_plan_id=billing_plan_id, 
        payment_gateway=payment_gateway)
    
    # GENERATE transaction reference
    tx_ref = f"{current_user.id}#{datetime.now(tz=timezone.utc).timestamp()}"

    # SET actual data for payment
    payment_data = {
        "tx_ref": tx_ref,
        "price": bill_plan.price,
        "redirect_url": f"{redirect_url}",
        "currency": bill_plan.currency,
        "user_email": current_user.email,
        "public_key": settings.RAVE_PUBLIC_KEY,
        "payment_title": "Convey AI Video Suites",
        "payment_description": "User subscription payment",
        "action_url": pg_service.FLUTTERWAVE_ONE_OFF_PAY_URL,
        "user_name": f"{current_user.first_name} {current_user.last_name}",
    }

    # RETURN payment data
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Payment data configured successfully",
        data=payment_data,
    )


@payment.get("/handle/{billing_plan_id}/{payment_gateway}", 
              status_code=status.HTTP_201_CREATED)
def handle_payment(
    billing_plan_id: str,
    payment_gateway: str,
    # product: PaymentCreate,
    request: Request,
    current_user: Annotated[User, Depends(user_service.get_current_user)],
    db: Session = Depends(get_db),
):
    """
    This handles responses from payment gateways
    """
    # CONFIRM payment_gateway
    if payment_gateway != "flutterwave":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Only fullterwave supported for now"
        )
    
    # GET billing plan
    bill_plan = bp_service.fetch(db, billing_plan_id)

    # GET response data
    resp_d = request.json()
    
    # CONFIRM flutterwave payment
    _ = pg_service.confirm_flutterwave_payment(current_user.id, resp_d, bill_plan)

    # INIT payment schema
    payment_schema = PaymentCreate(
        status="completed",
        method="flutterwave",
        user_id=current_user.id,
        amount=bill_plan.amount,
        currency=bill_plan.currency,
        transaction_id=resp_d['transaction_id']

    )

    # CREATE payment
    new_payment = payment_service.create(db=db, schema=payment_schema)

    # RETURN success response
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Payment added successfully",
        data=new_payment.to_dict(),
    )
    

@payment.get(
    "/current-user", status_code=status.HTTP_200_OK, response_model=PaymentListResponse
)
def get_payments_for_current_user(
    current_user: User = Depends(user_service.get_current_user),
    limit: Annotated[int, Query(ge=1, description="Number of payments per page")] = 10,
    page: Annotated[int, Query(ge=1, description="Page number (starts from 1)")] = 1,
    db: Session = Depends(get_db),
):
    """
    Endpoint to retrieve a paginated list of payments of ``current_user``.

    Query parameter:
        - limit: Number of payment per page (default: 10, minimum: 1)
        - page: Page number (starts from 1)
    """

    # FETCH all payments for current user
    payments = payment_service.fetch_by_user(
        db, user_id=current_user.id, limit=limit, page=page
    )

    # GET number of payments
    num_of_payments = len(payments)

    if not num_of_payments:
        # RETURN not found message
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payments not found for user"
        )

    # GET total number of pages based on number of payments/limit per page
    total_pages = int(num_of_payments / limit) + (num_of_payments % limit > 0)

    # COMPUTE payment data into a list
    payment_data = [
        {
            "amount": str(pay.amount),
            "currency": pay.currency,
            "status": pay.status,
            "method": pay.method,
            "created_at": pay.created_at.isoformat(),
        }
        for pay in payments
    ]

    # GATHER all data in a dict
    data = {
        "pagination": {
            "limit": limit,
            "current_page": page,
            "total_pages": total_pages,
            "total_items": num_of_payments,
        },
        "payments": payment_data,
        "user_id": current_user.id,
    }

    # RETURN all data with success message
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Payments fetched successfully",
        data=data,
    )


@payment.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: str, db: Session = Depends(get_db)):
    '''
    Endpoint to retrieve a payment by its ID.
    '''
    payment_service = PaymentService()
    payment = payment_service.get_payment_by_id(db, payment_id)
    return payment

