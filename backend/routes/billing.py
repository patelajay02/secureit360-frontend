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
                "status": "Trial",
                "max_domains": 1,
                "created_at": tenant_data.get("created_at"),
                "renewal_date": None,
            }

        sub = result.data[0]

        stripe_status = None
        if sub.get("stripe_subscription_id"):
            try:
                stripe_status = get_subscription(sub["stripe_subscription_id"])
            except Exception:
                pass

        return {
            "plan_name": sub.get("plan", "Starter"),
            "status": stripe_status["status"] if stripe_status else sub.get("status", "active"),
            "max_domains": sub.get("max_domains", 1),
            "created_at": sub.get("created_at"),
            "renewal_date": stripe_status["current_period_end"] if stripe_status else sub.get("current_period_end"),
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
        try:
            metadata = dict(data.metadata) if hasattr(data, "metadata") else {}
        except Exception:
            metadata = {}
        tenant_id = metadata.get("tenant_id")
        plan = metadata.get("plan", "starter")
        try:
            subscription_id = data.subscription if hasattr(data, "subscription") else None
        except Exception:
            subscription_id = None

        print(f"[WEBHOOK] tenant_id={tenant_id} plan={plan} subscription_id={subscription_id}")

        if tenant_id:
            try:
                supabase_admin.table("subscriptions").upsert({
                    "tenant_id": tenant_id,
                    "plan": plan,
                    "stripe_subscription_id": subscription_id,
                    "status": "active",
                    "max_domains": 3 if plan == "pro" else 10 if plan == "enterprise" else 1,
                }).execute()
                print(f"[WEBHOOK] Subscription upserted")
            except Exception as e:
                print(f"[WEBHOOK] Subscription upsert error: {e}")

            try:
                supabase_admin.table("tenants")\
                    .update({"status": "active", "plan": plan})\
                    .eq("id", tenant_id)\
                    .execute()
                print(f"[WEBHOOK] Tenant updated to active")
            except Exception as e:
                print(f"[WEBHOOK] Tenant update error: {e}")

    elif event_type == "customer.subscription.deleted":
        subscription_id = data.get("id")

        result = supabase_admin.table("subscriptions")\
            .select("tenant_id")\
            .eq("stripe_subscription_id", subscription_id)\
            .execute()

        supabase_admin.table("subscriptions")\
            .update({"status": "cancelled"})\
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
