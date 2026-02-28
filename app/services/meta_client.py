import httpx
from app.core.config import settings

class MetaClient:
    def __init__(self):
        # WhatsApp Config
        self.wa_access_token = settings.whatsapp_access_token
        self.phone_number_id = settings.whatsapp_phone_number_id
        self.wa_base_url = f"https://graph.facebook.com/v22.0/{self.phone_number_id}/messages"
        self.wa_headers = {
            "Authorization": f"Bearer {self.wa_access_token}",
            "Content-Type": "application/json",
        }
        
        # Messenger Config
        self.fb_token = settings.messenger_access_token
        
        # Instagram Config
        self.ig_token = settings.instagram_access_token

    async def send_whatsapp_message(self, recipient_id: str, text: str):
        """Sends a plain text message via WhatsApp Cloud API"""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_id,
            "type": "text",
            "text": {"body": text},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.wa_base_url, 
                json=payload, 
                headers=self.wa_headers
            )
            
            if response.status_code != 200:
                print(f"❌ WhatsApp Error: {response.text}")
            else:
                print(f"✅ WhatsApp reply sent to {recipient_id}")
            
            return response.json()
        
    async def send_messenger_message(self, recipient_id: str, text: str):
        """Sends a plain text message via Facebook Messenger API"""
        url = f"https://graph.facebook.com/v22.0/me/messages?access_token={self.fb_token}"
        
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": text}
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, 
                json=payload, 
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                print(f"❌ Messenger Error: {response.text}")
            else:
                print(f"✅ Messenger reply sent to {recipient_id}")
            
            return response.json()
            
# In app/services/meta_client.py
    async def send_instagram_message(self, recipient_id: str, text: str):
        url = "https://graph.facebook.com/v22.0/me/messages"
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": text},
            "access_token": self.ig_token  # Pass it here!
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            return response.json()