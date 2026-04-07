# backend/services/stripe_service.py
# SecureIT360 - Stripe payment service

import os
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

PRICE_IDS = {
    "starter": "price_1TJUKnHOFiRFdagYzzPaKk0W",
    "pro": "price_1TJUQoHOFiRFdagYAslEYNp7",
    "enterprise": "price_1TJUVLHOFiRFdagYTg26GvyI",
}

PLANS = {
    "starter": {
        "name": "Starter",
        "price_nzd": 250,
        "price_usd": 149,
        "domains_allowed": 1,
        "users_allowed": 3,
        "features": [
            "1 domain scanned daily",
            "6 security scan engines",
            "Ransom Risk Score",
            "Weekly director email",
            "Plain English findings",
            "Auto-fix simple issues",
        ],
    },
    "pro": {
        "name": "Pro",
        "price_nzd": 500,
        "price_usd": 299,
        "domains_allowed": 3,
        "users_allowed": 10,
        "features": [
            "3 domains scanned daily",
            "6 security scan engines",
            "Ransom Risk Score",
            "Weekly director email",
            "Plain English findings",
            "Auto-fix simple issues",
            "Voice-guided fix walkthroughs",
            "Compliance gap report",
            "Director evidence report",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "price_nzd": 840,
        "price_usd": 499,
        "domains_allowed": 10,
        "users_allowed": 999,
        "features": [
            "10 domains scanned daily",
            "6 security scan engines",
            "Ransom Risk Score",
            "Weekly director email",
            "Plain English findings",
            "Auto-fix simple issues",
            "Voice-guided fix walkthroughs",
            "Full compliance gap report",
            "Director evidence report",
            "ISO 27001 readiness report",
            "Essential Eight maturity report",
            "Priority specialist access",
            "Unlimited users",
        ],
    },
}


def create_customer(email: str, company_name: str) -> str:
    customer = stripe.Customer.create(
        email=email,
        name=company_name,
        metadata={"platform": "SecureIT360"},
    )
    return customer.id


def create_checkout_session(
    customer_id: str,
    plan: str,
    tenant_id: str,
    success_url: str,
    cancel_url: str,
) -> str:
    price_id = PRICE_IDS.get(plan)
    if not price_id:
        raise ValueError(f"Invalid plan: {plan}")

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        metadata={"tenant_id": tenant_id, "plan": plan},
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return session.url


def create_billing_portal_session(customer_id: str, return_url: str) -> str:
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


def get_subscription(subscription_id: str) -> dict:
    try:
        sub = stripe.Subscription.retrieve(subscription_id)
        return {
            "status": sub.status,
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
        }
    except Exception as e:
        print(f"Error getting subscription: {e}")
        return None


def construct_webhook_event(payload: bytes, sig_header: str) -> dict:
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        return event
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid webhook signature")


def get_plans():
    return PLANS