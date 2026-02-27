from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    meta_verify_token: str
    
    # WhatsApp
    whatsapp_access_token: str
    whatsapp_phone_number_id: str
    
    # Messenger
    messenger_access_token: str
    
    # Instagram
    instagram_access_token: str
    
    # LLM
    groq_api_key: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()