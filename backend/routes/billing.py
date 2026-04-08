# backend/routes/billing.py
# SecureIT360 - Billing routes
# Handles Stripe checkout, webhooks, and subscription management

import os
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from middleware.auth_middleware import get_current_tenant
from services.stripe_service import (
    create_customer,
    create_checkout_session,
    create_billing_portal_session,
    construct_webhook_event,
    get_subscription,
    get_plans,
)
from services.database import supabase_admin

router = APIRouter()

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://app.secureit360.co")


# --- Get Plans ----------------------------------------------------------

@router.get("/plans")
def get_available_plans():
    return get_plans()


# --- Get Current Subscription -------------------------------------------

@router.get("/subscription")
async def get_subscription_info(tenant=Depends(get_current_tenant)):
    try:
        tenant_id = tenant["tenant_id"]

        result = supabase_admin.table("subscriptions")\
            .select("*")\
            .eq("tenant_id", tenant_id)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()

        if not result.data:
            tenant_result = supabase_admin.table("tenants")\
                .select("*")\
                .eq("id", tenant_id)\
                .single()\
                .execute()

            tenant_data = tenant_result.data or {}
            return {
                "plan_name": "Trial",
                "price_nzd": "$0",
                "status": "Trial",
                "domains_allowed": 1,
                "created_at": tenant_data.get("created_at"),
                "renewal_date": None,
            }

        sub = result.data[0]

        stripe_status = None
        if sub.get("stripe_subscription_id"):
            stripe_status = get_subscription(sub["stripe_subscription_id"])

        return {
            "plan_name": sub.get("plan_name", "Starter"),
            "price_nzd": sub.get("price_nzd", "$250"),
            "status": stripe_status["status"] if stripe_status else sub.get("status", "active"),
            "domains_allowed": sub.get("domains_allowed", 1),
            "created_at": sub.get("created_at"),
            "renewal_date": stripe_status["current_period_end"] if stripe_status else sub.get("renewal_date"),
        }

    except Exception as e:
        print(f"Error getting subscription: {e}")
        raise HTTPException(status_code=500, detail="Could not load subscription info")


# --- Create Checkout Session --------------------------------------------

@router.post("/checkout/{plan}")
async def create_checkout(plan: str, tenant=Depends(get_current_tenant)):
    try:
        tenant_id = tenant["tenant_id"]
        user_id = tenant["user_id"]

        tenant_result = supabase_admin.table("tenants")\
            .select("*")\
            .eq("id", tenant_id)\
            .single()\
            .execute()

        tenant_data = tenant_result.data
        if not tenant_data:
            raise HTTPException(status_code=404, detail="Tenant not found")

        stripe_customer_id = tenant_data.get("stripe_customer_id")
        if not stripe_customer_id:
            auth_user = supabase_admin.auth.admin.get_user_by_id(user_id)
            owner_email = auth_user.user.email if auth_user and auth_user.user else ""

            stripe_customer_id = create_customer(
                email=owner_email,
                company_name=tenant_data.get("name", ""),
            )

            supabase_admin.table("tenants")\
                .update({"stripe_customer_id": stripe_customer_id})\
                .eq("id", tenant_id)\
                .execute()

        checkout_url = create_checkout_session(
            customer_id=stripe_customer_id,
            plan=plan,
            tenant_id=tenant_id,
            success_url=f"{FRONTEND_URL}/dashboard?subscribed=true",
            cancel_url=f"{FRONTEND_URL}/pricing",
        )

        return {"checkout_url": checkout_url}

    except Exception as e:
        print(f"Checkout error: {e}")
        raise HTTPException(status_code=500, detail="Could not create checkout session")


# --- Billing Portal -----------------------------------------------------

@router.post("/portal")
async def billing_portal(tenant=Depends(get_current_tenant)):
    try:
        tenant_id = tenant["tenant_id"]

        tenant_result = supabase_admin.table("tenants")\
            .select("stripe_customer_id")\
            .eq("id", tenant_id)\
            .single()\
            .execute()

        stripe_customer_id = tenant_result.data.get("stripe_customer_id")
        if not stripe_customer_id:
            raise HTTPException(status_code=400, detail="No billing account found")

        portal_url = create_billing_portal_session(
            customer_id=stripe_customer_id,
            return_url=f"{FRONTEND_URL}/settings?tab=billing",
        )

        return {"portal_url": portal_url}

    except Exception as e:
        print(f"Portal error: {e}")
        raise HTTPException(status_code=500, detail="Could not open billing portal")


# --- Stripe Webhook -----------------------------------------------------

@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = construct_webhook_event(payload, sig_header)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        tenant_id = data.get("metadata", {}).get("tenant_id")
        plan = data.get("metadata", {}).get("plan", "starter")
        subscription_id = data.get("subscription")

        if tenant_id:
            from services.stripe_service import PLANS
            plan_data = PLANS.get(plan, PLANS["starter"])

            supabase_admin.table("subscriptions").upsert({
                "tenant_id": tenant_id,
                "plan_name": plan_data["name"],
                "plan_key": plan,
                "price_nzd": plan_data["price_nzd"],
                "domains_allowed": plan_data["domains_allowed"],
                "users_allowed": plan_data["users_allowed"],
                "stripe_subscription_id": subscription_id,
                "status": "active",
            }).execute()

            supabase_admin.table("tenants")\
                .update({"status": "active", "plan": plan})\
                .eq("id", tenant_id)\
                .execute()

    elif event_type == "customer.subscription.deleted":
        subscription_id = data.get("id")
        supabase_admin.table("subscriptions")\
            .update({"status": "cancelled"})\
            .eq("stripe_subscription_id", subscription_id)\
            .execute()

        result = supabase_admin.table("subscriptions")\
            .select("tenant_id")\
            .eq("stripe_subscription_id", subscription_id)\
            .execute()
        if result.data:
            supabase_admin.table("tenants")\
                .update({"status": "cancelled"})\
                .eq("id", result.data[0]["tenant_id"])\
                .execute()

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        tenant_result = supabase_admin.table("tenants")\
            .select("id")\
            .eq("stripe_customer_id", customer_id)\
            .execute()

        if tenant_result.data:
            tenant_id = tenant_result.data[0]["id"]
            supabase_admin.table("subscriptions")\
                .update({"status": "past_due"})\
                .eq("tenant_id", tenant_id)\
                .execute()
            supabase_admin.table("tenants")\
                .update({"status": "past_due"})\
                .eq("id", tenant_id)\
                .execute()

    return JSONResponse(content={"received": True})
