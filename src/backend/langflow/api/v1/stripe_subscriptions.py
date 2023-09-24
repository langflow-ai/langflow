import stripe

from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.user.user import User
from fastapi import APIRouter, Depends

# build router
router = APIRouter(prefix="/stripe_subscription", tags=["Stripe"])


@router.post("/attempt/{price_id}", status_code=200)
def attempt_subscribe(
    price_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Create a new flow."""
    try:
        checkout_session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[
                {
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            success_url="http://localhost:3000",
            cancel_url="http://localhost:3000/payment",
            customer=current_user.stripe_id,
        )
    except Exception as e:
        return str(e)

    return checkout_session.url
