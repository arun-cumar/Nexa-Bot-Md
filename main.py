hereimport os
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import MessagesFilter 
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, Document, Video, Audio
from pyrogram.errors import UserNotParticipant
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from typing import List, Dict, Any, Union
from fastapi import FastAPI, Request, Response
from contextlib import asynccontextmanager
from http import HTTPStatus
import uvicorn

# Loading variables from .env file (for local testing)
load_dotenv()

# --- Config Variables ---
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
PRIVATE_FILE_STORE = int(os.environ.get("PRIVATE_FILE_STORE", -100))
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", -100))

# Creating ADMINS list
ADMINS = []
admin_env = os.environ.get("ADMINS", "")
if admin_env:
    ADMINS = [int(admin.strip()) for admin in admin_env.split(',') if admin.strip().isdigit()]

DATABASE_URL = os.environ.get("DATABASE_URL", "mongodb://localhost:27017")
FORCE_SUB_CHANNEL = os.environ.get("FORCE_SUB_CHANNEL", None)

# Webhook Details
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL_BASE", None)
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_PATH = f"/{BOT_TOKEN}"

# --- MongoDB Setup ---

class Database:
    """Handles database operations."""
    def __init__(self, uri: str, database_name: str):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.files_col = self.db["files"]

    async def get_all_files(self) -> List[Dict[str, Any]]:
        """Returns all file entries in the database as a list."""
        cursor = self.files_col.find({})
        return await cursor.to_list(length=None)

    async def find_one(self, query: Dict[str, Any]) -> Dict[str, Any] | None:
        return await self.files_col.find_one(query)

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        await self.files_col.update_one(query, update, upsert=upsert)

# Database instance
db = Database(DATABASE_URL, "AutoFilterBot")

# --- Pyrogram Client ---
class AutoFilterBot(Client):
    def __init__(self):
        super().__init__(
            "AutoFilterBot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins=dict(root="plugins"),
            sleep_threshold=30
        )

# --- Bot Instance (Global Pyrogram Client) ---
app = AutoFilterBot()

# --- Helpers ---

async def is_subscribed(client, user_id):
    """Checks if the user is a member of the force subscribe channel."""
    if not FORCE_SUB_CHANNEL:
        return True
    try:
        member = await client.get_chat_member(FORCE_SUB_CHANNEL, user_id) 
        if member.status in ["member", "administrator", "creator"]:
            return True
        return False
    except UserNotParticipant:
        print("DEBUG: User not participant in force sub channel.")
        return False
    except Exception as e:
        print(f"Error checking subscription: {e}")
        return True 

async def get_file_details(query):
    """Searches for file information from the database."""
    
    # DEBUG: Log the search query
    print(f"DEBUG: Searching for query: '{query}'")

    cursor = db.files_col.find({ 
        "$or": [
            {"title": {"$regex": query, "$options": "i"}},
            {"caption": {"$regex": query, "$options": "i"}}
        ]
    }).limit(10)
    
    files = await cursor.to_list(length=10)
    
    # DEBUG: Log the number of files found
    print(f"DEBUG: Found {len(files)} files for query: '{query}'")
    
    return files

# --- Handlers ---

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    await message.reply_text(
        "👋 Hi! I am an Auto-Filter Bot. If you add me to your group, I will send the files requested in the group. Please contact the developer for more information."
    )

@app.on_message(filters.command("dbcount") & filters.user(ADMINS))
async def db_count_command(client, message: Message):
    """Checks how many files are in the database."""
    try:
        count_message = await message.reply_text("Fetching database count, please wait...")
        files_count = await db.files_col.count_documents({})
        await count_message.edit_text(f"📊 Currently indexed files count in database: **{files_count}**")
    except Exception as e:
        await message.reply_text(f"❌ Database connection error occurred: {e}")

def get_file_info(message: Message) -> tuple[str, str, Union[Document, Video, Audio, None]]:
    """Finds file_id, file_name, and file_object from the message."""
    # Note: To exclude if message.document.file_name is missing
    if message.document and message.document.file_name:
        return message.document.file_id, message.document.file_name, message.document
    if message.video:
        # If video lacks file_name, use caption or id
        file_name = message.caption.strip() if message.caption else f"Video_{message.id}"
        return message.video.file_id, file_name, message.video
    if message.audio:
        # If audio lacks file_name/title, use id
        file_name = message.audio.file_name or message.audio.title or f"Audio_{message.id}"
        return message.audio.file_id, file_name, message.audio
    return None, None, None

@app.on_message(filters.command("index") & filters.user(ADMINS))
async def index_command(client, message: Message):
    """Command for Admins to index files in the file store channel."""
    if PRIVATE_FILE_STORE == -100:
        await message.reply_text("PRIVATE_FILE_STORE ID is not provided in the ENV variable. Indexing is not possible.")
        return

    msg = await message.reply_text("Starting file indexing... (Check logs)")
    
    total_files_indexed = 0
    total_messages_processed = 0
    
    try:
        # search_messages is a generator
        async for chat_msg in client.search_messages(chat_id=PRIVATE_FILE_STORE, filter=MessagesFilter.ALL, limit=1000):
            total_messages_processed += 1
            file_id, file_name, file_object = get_file_info(chat_msg)
            
            if file_id and file_name:
                caption = chat_msg.caption.html if chat_msg.caption else None 
                
                try:
                    await db.files_col.update_one( 
                        {"file_id": file_id},
                        {
                            "$set": {
                                "title": file_name,
                                "caption": caption,
                                "file_id": file_id,
                                "chat_id": PRIVATE_FILE_STORE,
                                "message_id": chat_msg.id,
                                "media_type": file_object.__class__.__name__.lower()
                            }
                        },
                        upsert=True
                    )
                    total_files_indexed += 1
                    
                    if total_files_indexed % 50 == 0:
                         await msg.edit_text(f"✅ Indexed files: {total_files_indexed} / {total_messages_processed}")
                         print(f"INDEX_DEBUG: Successfully indexed {file_name}")

                except Exception as db_error:
                    # Error occurred while writing to the database
                    print(f"INDEX_DEBUG: DB WRITE ERROR for file {file_name}: {db_error}")
            else:
                # If file type is not Document, Video, or Audio
                if chat_msg.text:
                     # No need to index text messages
                    print(f"INDEX_DEBUG: Skipping Text message {chat_msg.id}")
                else:
                    # Other media types (Photo, Sticker, GIF)
                    print(f"INDEX_DEBUG: Skipping message {chat_msg.id} - Not a supported file type (Doc/Vid/Aud).")
            
        # Final report after indexing is complete
        await msg.edit_text(f"🎉 Indexing complete! Total {total_files_indexed} files added. ({total_messages_processed} messages checked)")
        
    except Exception as general_error:
        # Major errors like channel access issues
        await msg.edit_text(f"❌ Indexing Error: {general_error}. Check if the bot is a member of the channel and the ID is correct.")
        print(f"INDEX_DEBUG: FATAL INDEXING ERROR: {general_error}")


# Auto-Filter and Copyright Handler (Global)
@app.on_message(filters.text & filters.incoming & ~filters.command(["start", "index", "dbcount"])) 
async def global_handler(client, message: Message):
    """Handles all text messages: Copyright Delete & Auto-Filter."""
    query = message.text.strip()
    chat_id = message.chat.id
    
    # DEBUG: Log that the message reached the handler
    print(f"DEBUG: Incoming text from chat {chat_id}: '{query}'")
    
    # --- 1. Copyright message deletion logic (in all chats) ---
    COPYRIGHT_KEYWORDS = ["copyright", "unauthorized", "DMCA", "piracy"] 
    
    is_copyright_message = any(keyword.lower() in query.lower() for keyword in COPYRIGHT_KEYWORDS)
    is_protected_chat = chat_id == PRIVATE_FILE_STORE or chat_id in ADMINS
    
    if is_copyright_message and is_protected_chat:
        try:
            await message.delete()
            await client.send_message(LOG_CHANNEL, f"🚫 **Copyright Message Deleted!**\n\n**Chat ID:** `{chat_id}`\n**User:** {message.from_user.mention}\n**Message:** `{query}`")
            return
        except Exception as e:
            print(f"Error deleting copyright message in chat {chat_id}: {e}")
            return
    
    print(f"DEBUG: Passed copyright check. Proceeding to filter.")
            
    # --- 2. Auto-Filter search (except in the file store channel) ---
    
    if chat_id == PRIVATE_FILE_STORE:
        print("DEBUG: Message came from PRIVATE_FILE_STORE, skipping filter.")
        return
        
    is_private = message.chat.type == "private"
    
    # Force Subscribe Check
    if not is_private or await is_subscribed(client, message.from_user.id):
        
        files = await get_file_details(query)
        
        if files:
            # Sends inline buttons if a file is found
            text = f"Here are the files related to your search for **{query}**:\n\n"
            buttons = []
            for file in files:
                media_icon = {"document": "📄", "video": "🎬", "audio": "🎶"}.get(file.get('media_type', 'document'), '❓')
                # Tries to get the clean file name for the button text
                file_name = file.get("title", "File").rsplit('.', 1)[0].strip() 
                
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{media_icon} {file_name}",
                        callback_data=f"getfile_{file.get('file_id')}" 
                    )
                ])
            
            if len(files) == 10:
                 buttons.append([InlineKeyboardButton("More Results", url="https://t.me/your_search_group")]) 

            sent_message = await message.reply_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=True
            )
            
            print(f"DEBUG: Filter results sent for query '{query}'. Starting autodelete timer.")
            
            # --- Autodelete Logic (After 1 minute) ---
            await asyncio.sleep(60)
            try:
                await sent_message.delete()
                print("DEBUG: Autodelete completed.")
            except Exception as e:
                print(f"Error during autodelete: {e}")
                
    elif is_private:
        # If not force subscribed
        if not FORCE_SUB_CHANNEL: return
        
        join_button = [
            [InlineKeyboardButton("Join Channel", url=f"https://t.me/{FORCE_SUB_CHANNEL.replace('@', '')}")]
        ]
        await message.reply_text(
            f"If you want to receive files, you must first join our channel.",
            reply_markup=InlineKeyboardMarkup(join_button)
        )

# --- Callback Query Handler (Inline Button Click) ---

@app.on_callback_query(filters.regex("^getfile_"))
async def send_file_handler(client, callback):
    """Sends the file when the button is clicked."""
    
    # Force Subscribe Check
    if FORCE_SUB_CHANNEL and not await is_subscribed(client, callback.from_user.id):
        await callback.answer("Join the channel to get the file.", show_alert=True)
        return

    file_id = callback.data.split("_")[1]
    file = await db.files_col.find_one({"file_id": file_id}) 
    
    if file:
        try:
            # Forwards the file from the original store channel
            await client.forward_messages(
                chat_id=callback.message.chat.id,
                from_chat_id=file['chat_id'],
                message_ids=file['message_id']
            )
            await callback.answer("File sent.", show_alert=False)
        except Exception as e:
            await callback.answer("An error occurred while sending the file. Check if the bot has access.", show_alert=True)
            print(f"File forward error: {e}")
    else:
        await callback.answer("File was removed from the database.", show_alert=True)
    
    try:
        await callback.message.delete()
    except Exception as e:
        print(f"Error deleting inline message: {e}")

# --- Render Webhook Setup (FastAPI for a scalable deployment) ---

# --- STARTUP/SHUTDOWN Lifecycle ---
async def startup_initial_checks():
    """Initial checks to run on startup."""
    print("Running initial startup checks...")
    try:
        files_count = await db.files_col.count_documents({})
        print(f"Database check completed. Found {files_count} files in the database.")
    except Exception as e:
        print(f"Warning: Database check failed during startup: {e}")


@asynccontextmanager
async def lifespan(web_app: FastAPI):
    await startup_initial_checks()
    
    if WEBHOOK_URL_BASE:
        await app.start() 
        await app.set_webhook(url=f"{WEBHOOK_URL_BASE}{WEBHOOK_PATH}")
        print(f"Webhook set successfully to: {WEBHOOK_URL_BASE}{WEBHOOK_PATH}")
    else:
        await app.start()
        print("Starting in Polling Mode (for local testing only).")
        
    yield
    await app.stop()
    print("Application stopped.")

# FastAPI instance (Global variable 'api_app' used in uvicorn command)
api_app = FastAPI(lifespan=lifespan)

# Webhook endpoint for Telegram updates
@api_app.post(WEBHOOK_PATH)
async def process_update(request: Request):
    """Receives Telegram updates."""
    try:
        req = await request.json()
        await app.process_update(req)
        return Response(status_code=HTTPStatus.OK)
    except Exception as e:
        print(f"Error processing update: {e}")
        return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

# Health Check endpoint for Render
@api_app.get("/")
async def health_check():
    """Render Health Check."""
    return {"status": "ok"}

# --- Main Entry Point ---

if __name__ == "__main__":
    if WEBHOOK_URL_BASE:
        uvicorn.run("autofilter_bot:api_app", host="0.0.0.0", port=PORT, log_level="info")
    else:
        print("Starting Pyrogram in Polling Mode...")
        asyncio.run(startup_initial_checks())
        app.run()
