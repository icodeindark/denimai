from groq import Groq
from app.core.config import settings

def test_groq_connection():
    print("🔑 Verifying API Key from .env...")
    
    try:
        # We use the settings object we created earlier to securely load the key
        client = Groq(api_key=settings.groq_api_key)
        
        print("🧠 Sending test prompt to Llama 3...")
        
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system", 
                    "content": "You are the AI brain for DenimAI, a cool jeans store."
                },
                {
                    "role": "user", 
                    "content": "Say exactly: 'Hello, DenimAI is online and ready to sell some jeans!'"
                }
            ],
            model="llama-3.3-70b-versatile", # Groq's insanely fast and free Llama 3 model
        )
        
        print("\n✅ SUCCESS! Groq responded:")
        print("-" * 50)
        print(response.choices[0].message.content)
        print("-" * 50)

    except Exception as e:
        print(f"\n❌ ERROR connecting to Groq: {e}")
        print("Check if your GROQ_API_KEY in the .env file is correct.")

if __name__ == "__main__":
    test_groq_connection()