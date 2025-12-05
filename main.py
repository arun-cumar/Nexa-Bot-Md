import os
from pyrogram import Client
from dotenv import load_dotenv

# Load API_ID and API_HASH from the .env file
load_dotenv()

API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")

if not API_ID or not API_HASH:
    print("API_ID and API_HASH must be provided in the .env file.")
    exit()

async def generate_session_string():
    """Generates the Pyrogram User Session String."""
    print("Starting Pyrogram User Session generation...")
    
    # Create a user client with the required credentials
    async with Client(
        name="my_user_session", 
        api_id=int(API_ID), 
        api_hash=API_HASH, 
        # Note: Do not include bot_token for user sessions
    ) as user_client:
        # Export the session string
        session_string = await user_client.export_session_string()
        print("\n" + "="*50)
        print("✅ User Session String generated successfully:")
        print("THIS IS A HIGHLY SENSITIVE STRING. DO NOT SHARE IT.")
        print(session_string)
        print("="*50 + "\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_session_string())

