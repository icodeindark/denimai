# app/api/webhook.py
#
# UPDATED: Now calls run_agent() instead of the placeholder reply.
# This is the final connection — Meta → webhook → LangGraph → reply → Meta

from fastapi import APIRouter, Request, Response, Query, HTTPException, BackgroundTasks
from app.core.config import settings
from app.services.normalization import normalize_meta_payload
from app.services.meta_client import MetaClient
from app.agent.runner import run_agent  # ← The new import

router = APIRouter()
meta_client = MetaClient()


@router.get("/webhook/meta")
async def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge"),
):
    """Handles the one-time Meta Webhook Verification Handshake."""
    print(f"\n🔐 Verification attempt | mode={mode} | token={token}")

    if mode == "subscribe" and token == settings.meta_verify_token:
        print("✅ Webhook verified!")
        return Response(content=challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Verification failed.")


@router.post("/webhook/meta")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """
    Receives all incoming messages from WhatsApp, Messenger, and Instagram.
    Returns 200 immediately to Meta, processes in background.
    """
    payload = await request.json()
    data = normalize_meta_payload(payload)

    if data:
        print(f"✅ [{data['platform'].upper()}] {data['user_name']}: '{data['text']}'")
        background_tasks.add_task(handle_reply, data)
    else:
        print("  ↳ Non-message webhook event. Ignoring.")

    return {"status": "ok"}


async def handle_reply(data: dict):
    """
    Runs the LangGraph agent and sends the reply back to the user.
    This is the only function that changed from the placeholder version.
    """
    # ── Run the AI agent ──────────────────────────────────────────────────────
    # run_agent() handles everything: memory, routing, tools, DB queries
    reply_text = await run_agent(
        thread_id=data["thread_id"],
        user_message=data["text"],
        platform=data["platform"],
        user_name=data.get("user_name", "Customer")
    )

    # ── Send the reply to the correct platform ────────────────────────────────
    platform = data["platform"]
    sender_id = data["sender_id"]

    if platform == "whatsapp":
        await meta_client.send_whatsapp_message(sender_id, reply_text)
    elif platform == "instagram":
        await meta_client.send_instagram_message(sender_id, reply_text)
    elif platform == "messenger":
        await meta_client.send_messenger_message(sender_id, reply_text)
    else:
        print(f"⚠️ Unknown platform: {platform}")