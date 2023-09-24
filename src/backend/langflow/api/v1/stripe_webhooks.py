import stripe

from fastapi import APIRouter, HTTPException, Request, Depends
from sqlmodel import Session
from langflow.services.database.models.user import UserUpdate
from langflow.services.database.models.user.crud import update_user, get_user_by_stripe_id
from langflow.services.getters import get_session

# build router
router = APIRouter(prefix="/stripe_webhooks", tags=["Stripe"])

subscription_change_events = [
    'customer.subscription.created',
    'customer.subscription.deleted',
    'customer.subscription.paused',
    'customer.subscription.resumed',
    'customer.subscription.trial_will_end',
    'customer.subscription.updated'
]


@router.post("", status_code=200)
async def stripe_webhooks(
        request: Request,
        session: Session = Depends(get_session),
):
    try:
        event = stripe.Event.construct_from(
            await request.json(), stripe.api_key
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event.type in subscription_change_events:
        subscription: stripe.Subscription = event.data.object

        user_update = UserUpdate(
            stripe_subscription_status=subscription.status
        )

        if user_db := get_user_by_stripe_id(session, subscription.customer):
            return update_user(user_db, user_update, session)
        else:
            raise HTTPException(status_code=404, detail="User not found")
    else:
        print('Unhandled event type {}'.format(event.type))
