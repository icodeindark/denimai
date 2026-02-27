# app/services/normalization.py
# 
# This file's job: Take the messy, inconsistent JSON that Meta sends
# and turn it into ONE clean, simple dictionary that the rest of our
# app can understand — regardless of whether it came from WhatsApp,
# Messenger, or Instagram.


def normalize_meta_payload(payload: dict):
    """
    Unified normalizer for WhatsApp, Messenger, and Instagram.

    Meta sends very different JSON structures depending on the platform.
    This function acts as a "translator" — it reads the messy input
    and always returns the same clean shape:

    {
        "platform": "whatsapp" | "messenger" | "instagram",
        "sender_id": "12345",
        "thread_id": "whatsapp_12345",   <-- unique key for LangGraph memory
        "text": "I want to buy jeans",
        "user_name": "Alex"
    }

    Returns None if the payload is not a user message we care about
    (e.g. Meta status pings, delivery receipts, echo messages, etc.)
    """

    # ---------------------------------------------------------------
    # STEP 1: Log the raw payload so you can debug on your server logs
    # ---------------------------------------------------------------
    # This is your best friend when things go wrong. Every payload
    # that hits your server will be printed to your terminal.
    object_type = payload.get("object", "UNKNOWN")
    print(f"\n📦 RAW WEBHOOK RECEIVED | object type: '{object_type}'")

    try:

        # -----------------------------------------------------------
        # ROUTE A: Messenger (Facebook Page messages)
        # Meta sends object = "page" for Messenger
        # -----------------------------------------------------------
        if object_type == "page":
            entry = payload["entry"][0]

            # Messenger uses a "messaging" array (not "changes")
            messaging_event = entry.get("messaging", [{}])[0]

            # Skip "echo" events — these are copies of YOUR OWN replies
            # coming back to you. Ignore them or you'll loop forever.
            if messaging_event.get("message", {}).get("is_echo"):
                print("  ↳ Skipping echo message from Messenger.")
                return None

            # Make sure it's a real text message (not a sticker/emoji/attachment)
            message_obj = messaging_event.get("message", {})
            if "text" not in message_obj:
                print(f"  ↳ Skipping non-text Messenger event (e.g. attachment, reaction).")
                return None

            sender_id = messaging_event["sender"]["id"]
            print(f"  ↳ Messenger message from sender_id: {sender_id}")

            return {
                "platform": "messenger",
                "sender_id": sender_id,
                "thread_id": f"messenger_{sender_id}",
                "text": message_obj["text"],
                "user_name": "Customer",  # Messenger webhooks rarely include the name
            }

        # -----------------------------------------------------------
        # ROUTE B: Instagram Direct Messages
        # Meta sends object = "instagram" for Instagram DMs
        # -----------------------------------------------------------
        if object_type == "instagram":
            entry = payload["entry"][0]

            # Instagram DMs also use the "messaging" structure
            messaging_event = entry.get("messaging", [{}])[0]

            # Skip echo messages (your own replies bouncing back)
            if messaging_event.get("message", {}).get("is_echo"):
                print("  ↳ Skipping echo message from Instagram.")
                return None

            message_obj = messaging_event.get("message", {})
            if "text" not in message_obj:
                print(f"  ↳ Skipping non-text Instagram event.")
                return None

            sender_id = messaging_event["sender"]["id"]
            print(f"  ↳ Instagram DM from sender_id: {sender_id}")

            return {
                "platform": "instagram",
                "sender_id": sender_id,
                "thread_id": f"instagram_{sender_id}",
                "text": message_obj["text"],
                "user_name": "Customer",
            }

        # -----------------------------------------------------------
        # ROUTE C: WhatsApp Cloud API
        # Meta sends object = "whatsapp_business_account" for WhatsApp.
        # The structure is completely different from A and B above.
        # -----------------------------------------------------------
        if object_type == "whatsapp_business_account":
            value = payload["entry"][0]["changes"][0]["value"]

            # WhatsApp sends "status" updates (delivered, read) in the same
            # webhook. These do NOT have a "messages" key. We skip them.
            if "messages" not in value:
                print(f"  ↳ Skipping WhatsApp status update (delivery/read receipt).")
                return None

            message = value["messages"][0]

            # Skip non-text messages (voice notes, images, etc.)
            if message.get("type") != "text":
                print(f"  ↳ Skipping non-text WhatsApp message. Type: {message.get('type')}")
                return None

            # contacts[0] holds the user's profile info
            contact = value.get("contacts", [{}])[0]
            sender_id = message["from"]  # This is the user's phone number
            user_name = contact.get("profile", {}).get("name", "Customer")

            print(f"  ↳ WhatsApp message from {user_name} ({sender_id})")

            return {
                "platform": "whatsapp",
                "sender_id": sender_id,
                "thread_id": f"whatsapp_{sender_id}",
                "text": message["text"]["body"],
                "user_name": user_name,
            }

        # -----------------------------------------------------------
        # FALLBACK: Unknown object type
        # -----------------------------------------------------------
        print(f"  ↳ ⚠️  Unrecognized object type: '{object_type}'. Ignoring payload.")
        return None

    except (KeyError, IndexError, TypeError) as e:
        # If ANYTHING goes wrong parsing the payload, log it clearly.
        # This tells you exactly what broke instead of silently failing.
        print(f"  ↳ ❌ NORMALIZATION ERROR: {type(e).__name__}: {e}")
        print(f"  ↳ Full payload was: {payload}")
        return None