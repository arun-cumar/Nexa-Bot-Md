import os 
import re
import asyncio
import json
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, Document, Video, Audio
from pyrogram.errors import UserNotParticipant, MessageNotModified, ChatAdminRequired, RPCError
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from typing import List, Dict, Any, Union
from fastapi import FastAPI, Request, Response 
from contextlib import asynccontextmanager
from http import HTTPStatus
import uvicorn

# Load variables from the .env file
load_dotenv()

# --- GLOBAL STATUS FLAG ---
IS_INDEXING_RUNNING = False

# --- CUSTOM CAPTION FOR SENT FILES ---
NEW_CAPTION = (
    "°•➤@Mala_Television 🍿\n"
    "°•➤@Mala_Tv\n"
    "°•➤@MalaTvbot ™️\n\n"
    "🙂🙂"
)

# --- CONFIG VARIABLES ---
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
# Channel ID where files are stored (MUST be private)
PRIVATE_FILE_STORE = int(os.environ.get("PRIVATE_FILE_STORE", -100)) 
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", -100))
# Pyrogram session string for the user account used for indexing/forwarding protected content
USER_SESSION_STRING = os.environ.get("USER_SESSION_STRING", None) 

# Admin list
ADMINS = []
admin_env = os.environ.get("ADMINS", "")
if admin_env:
    ADMINS = [int(admin.strip()) for admin in admin_env.split(',') if admin.strip().isdigit()]

DATABASE_URL = os.environ.get("DATABASE_URL", "mongodb://localhost:27017")
# Force subscribe channel (e.g., @MyChannel)
FORCE_SUB_CHANNEL = os.environ.get("FORCE_SUB_CHANNEL", None) 

# Webhook details for Render/Cloud deployment
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL_BASE", None)
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_PATH = f"/{BOT_TOKEN}"

# --- MONGODB SETUP ---

class Database:
    """Handles database operations for storing file indexes."""
    def __init__(self, uri: str, database_name: str):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.files_col = self.db["files"]

    async def get_all_files(self) -> List[Dict[str, Any]]:
        """Returns all file entries as a list."""
        cursor = self.files_col.find({})
        return await cursor.to_list(length=None)

    async def find_one(self, query: Dict[str, Any]) -> Union[Dict[str, Any], None]:
        """Finds a single document matching the query."""
        return await self.files_col.find_one(query)

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        """Updates a single document. Inserts if upsert is True and no match is found."""
        await self.files_col.update_one(query, update, upsert=upsert)

# Database instance
db = Database(DATABASE_URL, "AutoFilterBot")

# --- PYROGRAM CLIENTS ---

# Bot Client
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

# Global Bot Instance
app = AutoFilterBot()

# Global User Client Instance (for indexing and protected content forwarding)
user_client: Union[Client, None] = None
if USER_SESSION_STRING:
    user_client = Client(
        "indexer_session",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=USER_SESSION_STRING, 
    )
    print("User session initialized for indexing/forwarding.")


# --- RENDER WEBHOOK SETUP (FastAPI) ---

async def startup_initial_checks():
    """Checks to run on startup."""
    print("Performing initial startup checks...")
    
    # 1. Database check
    try:
        files_count = await db.files_col.count_documents({})
        print(f"Database check complete. Found {files_count} files in the database.")
    except Exception as e:
        print(f"WARNING: Database connection failed on startup: {e}")
        
    # 2. Force Sub Admin check (CRITICAL)
    if FORCE_SUB_CHANNEL:
        print(f"FORCE_SUB_CHANNEL is set to: {FORCE_SUB_CHANNEL}. Verifying bot administration status...")
        
@asynccontextmanager
async def lifespan(web_app: FastAPI):
    # Run checks only once when the bot starts
    await startup_initial_checks()
    
    if WEBHOOK_URL_BASE:
        # Start Pyrogram client and set webhook
        await app.start() 
        if user_client: # Start user client for forwarding/indexing
            await user_client.start()
            
        await app.set_webhook(url=f"{WEBHOOK_URL_BASE}{WEBHOOK_PATH}")
        print(f"Webhook successfully set: {WEBHOOK_URL_BASE}{WEBHOOK_PATH}")
    else:
        # Start in polling mode (local testing)
        await app.start()
        if user_client:
            await user_client.start()
        print("Starting in polling mode (for local testing only).")
        
    yield
    await app.stop()
    if user_client:
         await user_client.stop()
    print("Application stopped.")

# FastAPI instance (CRITICAL: Defined at module level for Uvicorn)
api_app = FastAPI(lifespan=lifespan)

# Webhook endpoint for Telegram updates
@api_app.post(WEBHOOK_PATH)
async def process_update(request: Request):
    """Receives and processes Telegram updates."""
    try:
        req = await request.json()
        await app.process_update(req)
        return Response(status_code=HTTPStatus.OK)
    except Exception as e:
        print(f"Error processing update: {e}")
        return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

# Render health check endpoint
@api_app.get("/")
async def health_check():
    """Render health check endpoint."""
    return {"status": "ok"}


# --- HELPERS ---

async def is_subscribed(client, user_id, max_retries=3, delay=1):
    """
    Checks if the user is a member of the force subscribe channel, with retries.
    """
    if not FORCE_SUB_CHANNEL:
        return True
    
    for attempt in range(max_retries):
        try:
            member = await client.get_chat_member(FORCE_SUB_CHANNEL, user_id) 
            if member.status in ["member", "administrator", "creator"]:
                return True
            
            return False 
        
        except UserNotParticipant:
            if attempt < max_retries - 1:
                await asyncio.sleep(delay) 
            else:
                return False 
        except ChatAdminRequired:
             print("ERROR: Bot needs to be an admin in the FORCE_SUB_CHANNEL to check membership.")
             return False
        except Exception as e:
            print(f"Error checking subscription (Attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(delay) 
            else:
                 return False
            
    return False

async def get_file_details(query: str):
    """
    Searches for file details in the database using advanced tokenization and Regex.
    """
    
    # 1. Prepare for Advanced Search: Tokenize the query
    words = [word.strip() for word in re.split(r'\W+', query) if len(query.strip()) > 2 and len(word.strip()) > 1]
    
    # --- Search Logic 1: All tokens must be present (Order agnostic) ---
    all_word_conditions = []
    if words:
        for word in words:
            word_regex = re.escape(word)
            all_word_conditions.append({
                "$or": [
                    {"title": {"$regex": f".*\\b{word_regex}\\b.*", "$options": "i"}},
                    {"caption": {"$regex": f".*\\b{word_regex}\\b.*", "$options": "i"}}
                ]
            })

    # --- Search Logic 2: Simple Phrase Match (Fallback/Boost) ---
    escaped_query = re.escape(query)
    phrase_regex = f".*{escaped_query}.*"
    phrase_condition = {
        "$or": [
            {"title": {"$regex": phrase_regex, "$options": "i"}},
            {"caption": {"$regex": phrase_regex, "$options": "i"}}
        ]
    }

    if all_word_conditions:
        search_query = {
            "$or": [
                {"$and": all_word_conditions}, 
                phrase_condition             
            ]
        }
    else:
        search_query = phrase_condition
        
    cursor = db.files_col.find(search_query).limit(10)
    files = await cursor.to_list(length=10)
    
    return files

# Function to extract file details
def get_file_info(message: Message) -> tuple[Union[str, None], Union[str, None], Union[Document, Video, Audio, None]]:
    """Finds file_id, file_name, and file_object from a message."""
    if message.document and message.document.file_name:
        return message.document.file_id, message.document.file_name, message.document
    if message.video:
        file_name = message.caption.strip() if message.caption else f"Video_{message.id}"
        if message.video.file_name: # Use actual file name if available
             file_name = message.video.file_name
        return message.video.file_id, file_name, message.video
    if message.audio:
        file_name = message.audio.file_name or message.audio.title or f"Audio_{message.id}"
        return message.audio.file_id, file_name, message.audio
    return None, None, None

# --- START COMMAND ---
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    """Handles the /start command in a private chat."""
    global IS_INDEXING_RUNNING
    
    if IS_INDEXING_RUNNING:
        await message.reply_text("Indexing is currently running. Please wait until it is complete.")
        return
        
    start_text = (
        "Hi! I am your **Auto Filter Bot.** 🤩\n\n"
        "🔎 **How to use me?**\n"
        "1. Type the name of the movie or series you want in any group or channel where I am an admin.\n"
        "2. Click the result button that appears.\n"
        "3. The file will be sent to this Private Chat (DM) immediately! 🎉\n\n"
        "⚠️ **Note:** To receive files, you must first send **/start** in this private chat and talk to me. Then click the button in the group/channel.\n\n"
        "🔗 **Our Channels:**\n"
        "°•➤ @Mala_Television\n"
        "°•➤ @Mala_Tv\n"
        "°•➤ @MalaTvbot ™️\n\n"
        "**Admin Commands:**\n"
        "• `/index` - To index all files in the channel.\n"
        "• `/dbcount` - To check the number of files in the database."
    )
    
    await message.reply_text(start_text)

# --- ADMIN COMMANDS (Indexing uses user_client) ---

@app.on_message(filters.command("index") & filters.user(ADMINS))
async def index_command(client, message: Message):
    """
    Command to index all files from the file store channel using the user session.
    """
    global IS_INDEXING_RUNNING
    global user_client

    if IS_INDEXING_RUNNING:
        await message.reply_text("❌ Note: The indexing process is currently running. Please wait until it is complete.")
        return

    if PRIVATE_FILE_STORE == -100:
        await message.reply_text("PRIVATE_FILE_STORE ID is not provided in ENV. Indexing is not possible.")
        return
    
    if not USER_SESSION_STRING or not user_client:
         await message.reply_text("❌ Indexing Error: **USER_SESSION_STRING** is missing. Please provide the user session string.")
         return

    IS_INDEXING_RUNNING = True 
    
    msg = await message.reply_text("🔑 Starting file indexing using the user session... This may take some time. (Check logs)")
    
    total_files_indexed = 0
    total_messages_processed = 0
    
    try:
        # Check if user_client is started. If not, start it temporarily for the indexing process.
        if not user_client.is_running:
            await user_client.start() 

        # Iterate through all messages using Pyrogram's get_chat_history
        async for chat_msg in user_client.get_chat_history(chat_id=PRIVATE_FILE_STORE): 
            total_messages_processed += 1
            file_id, file_name, file_object = get_file_info(chat_msg)
            
            if file_id and file_name:
                caption = chat_msg.caption.html if chat_msg.caption else None 
                
                try:
                    # Save/update file details in MongoDB
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
                         try:
                             await msg.edit_text(f"✅ Indexed Files: {total_files_indexed} / {total_messages_processed}")
                         except MessageNotModified:
                             pass 

                except Exception as db_error:
                    print(f"INDEX_DEBUG: DB WRITE error for file {file_name}: {db_error}")
            else:
                if chat_msg.text:
                    print(f"INDEX_DEBUG: Skipping text message {chat_msg.id}")
                else:
                    print(f"INDEX_DEBUG: Skipping message {chat_msg.id} - Not a supported file type (Doc/Vid/Aud).")
            
        # Final report after indexing is complete
        await msg.edit_text(f"🎉 Indexing complete! Total {total_files_indexed} files added or updated. ({total_messages_processed} messages checked)")
        
    except Exception as general_error:
        await msg.edit_text(f"❌ Indexing Error: {general_error}. Please check if the user account has access to the channel and the ID is correct.")
        
    finally:
        # Do not stop user_client here if it's needed for forwarding
        IS_INDEXING_RUNNING = False

@app.on_message(filters.command("dbcount") & filters.user(ADMINS))
async def dbcount_command(client, message: Message):
    """Command to check the total number of files in the database."""
    try:
        count = await db.files_col.count_documents({})
        await message.reply_text(f"📊 **Database Count:**\nTotal indexed files: **{count}**")
    except Exception as e:
        await message.reply_text(f"❌ Error getting database count: {e}")

# Auto-filter and Copyright Handler (Global)
@app.on_message(filters.text & filters.incoming & ~filters.command(["start", "index", "dbcount"])) 
async def global_handler(client, message: Message):
    """Handles all incoming text messages: copyright deletion and auto-filter search."""
    query = message.text.strip()
    chat_id = message.chat.id
    chat_type = message.chat.type
    
    # Check if indexing is running
    global IS_INDEXING_RUNNING
    if IS_INDEXING_RUNNING:
        # Only reply to admins if indexing is running, ignore others to reduce spam
        if message.from_user.id in ADMINS:
            await message.reply_text("Indexing is running. Please try again when the process is complete.")
        return
    
    # --- 1. COPYRIGHT MESSAGE DELETION LOGIC ---
    COPYRIGHT_KEYWORDS = ["copyright", "unauthorized", "DMCA", "piracy"] 
    is_copyright_message = any(keyword.lower() in query.lower() for keyword in COPYRIGHT_KEYWORDS)
    is_protected_chat = chat_id == PRIVATE_FILE_STORE or chat_id in ADMINS
    
    if is_copyright_message and is_protected_chat:
        try:
            await message.delete()
            # Log the deletion
            await client.send_message(LOG_CHANNEL, f"🚫 **Copyright message deleted!**\n\n**Chat ID:** `{chat_id}`\n**User:** {message.from_user.mention}\n**Message:** `{query}`")
            return
        except Exception as e:
            print(f"Error deleting copyright message in chat {chat_id}: {e}")
            return
            
    # --- 2. AUTO-FILTER SEARCH (ONLY IN GROUPS/CHANNELS) ---
    
    if chat_type == ChatType.PRIVATE:
        # Instruction for private chat search
        await message.reply_text("👋 To search for files, please go to a group or channel where I am an admin and type the name. Click the button that appears to get the file here.")
        return
        
    if chat_id == PRIVATE_FILE_STORE:
        return
        
    # --- SEARCH IN GROUPS AND CHANNELS ---
    
    files = await get_file_details(query)
    
    if files:
        # Files found: Send inline buttons
        text = f"✅ **Results for {query}:**\n\nClick the button below to get the file. The file will be sent to your Private Chat (DM)."
        buttons = []
        # --- START BUTTON GENERATION LOOP ---
        for file in files:
            media_icon = {"document": "📄", "video": "🎬", "audio": "🎵"}.get(file.get('media_type', 'document'), '❓')
            file_name_clean = file.get("title", "File").rsplit('.', 1)[0].strip() 
            
            # One button per file
            buttons.append([
                InlineKeyboardButton(
                    text=f"{media_icon} {file_name_clean}",
                    callback_data=f"getmsg_{file.get('message_id')}" 
                )
            ])
        # --- END BUTTON GENERATION LOOP ---
        
        if len(files) == 10:
             buttons.append([InlineKeyboardButton("More Results ➡️", url="https://t.me/your_search_group")]) 

        sent_message = await message.reply_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
        
        # --- AUTODELETE LOGIC (after 60 seconds) ---
        await asyncio.sleep(60)
        try:
            # This deletes the search results message after 60 seconds if not clicked
            await sent_message.delete()
        except Exception as e:
            print(f"Error during autodelete: {e}")
    else:
        # Optional: Reply if nothing found to indicate the search completed
        # await message.reply_text(f"❌ Sorry, no files found for '{query}'.", quote=True)
        pass
                
# --- CALLBACK QUERY HANDLER (INLINE BUTTON CLICK) ---

async def handle_send_file(client, user_id, message_id, delete_message_id=None, delete_chat_id=None):
    """
    Core function to copy/forward the file content with fallback.
    """
    
    file = await db.files_col.find_one({"message_id": message_id}) 
    
    if not file:
        # Ensure error message is sent immediately if file not found
        try:
            await client.send_message(user_id, "❌ Sorry, this file has been removed from the database.")
        except Exception:
            pass
        return False, "File removed."

    # --- 1. Attempt to Copy the File (Bot client) ---
    try:
        # Pyrogram copy_message uses singular 'message_id' and accepts a custom caption
        await client.copy_message(
            chat_id=user_id, 
            from_chat_id=file['chat_id'],
            message_id=file['message_id'],
            caption=NEW_CAPTION # Custom caption added here
        )
        
        # Delete the original group filter message if needed (after successful delivery)
        if delete_message_id and delete_chat_id:
            try:
                await client.delete_messages(delete_chat_id, delete_message_id)
            except Exception as e:
                print(f"Error deleting original group message: {e}")

        return True, "File sent successfully via copy."
        
    except RPCError as e:
        print(f"RPC Error copying file to user {user_id}: {e}")
        
        # --- 2. FALLBACK: Attempt to Forward using User Session ---
        global user_client
        if user_client and (
            "MESSAGE_PROTECTED" in str(e).upper() or # Common error for protected content
            "PEER_ID_INVALID" in str(e).upper() or # Sometimes caused by user block
            "MESSAGE_ID_INVALID" in str(e).upper() # Sometimes related to inaccessible messages
        ):
            print(f"Falling back to user session forwarding for user {user_id}...")
            try:
                # Ensure user_client is running before using it for forwarding
                if not user_client.is_running:
                     await user_client.start()
                
                # forward_messages expects a LIST of IDs for 'message_ids' (does NOT support custom caption)
                await user_client.forward_messages(
                    chat_id=user_id, 
                    from_chat_id=file['chat_id'], 
                    message_ids=[file['message_id']] 
                )
                
                # Delete the original group filter message if needed (after successful delivery)
                if delete_message_id and delete_chat_id:
                    try:
                        await client.delete_messages(delete_chat_id, delete_message_id)
                    except Exception:
                        pass
                        
                return True, "File forwarded successfully via user session."
            except Exception as forward_e:
                print(f"Fallback forwarding failed for user {user_id}: {forward_e}")
                # Fallback failed, proceed to final error message
        
        # --- 3. Final Error Message (After all failures) ---
        error_msg = ("❌ **Sorry, the file could not be sent!** ❌\n\n"
                     "To resolve this issue, please ensure the following:\n"
                     "1. If you have blocked me, unblock me immediately and send **/start** again.\n"
                     "2. Check your Private Chat settings to ensure you allow files from bots.\n\n"
                     "Please try again by sending **/start**.")
        try:
            await client.send_message(user_id, error_msg)
        except Exception:
            pass # Cannot send error message if user blocked the bot
            
        return False, error_msg
        
    except Exception as e:
        print(f"Unexpected error copying file to user {user_id}: {e}")
        error_msg = "❌ An unexpected error occurred while sending the file. (Failed to copy file)"
        try:
            await client.send_message(user_id, error_msg)
        except Exception:
            pass
        return False, error_msg


@app.on_callback_query(filters.regex("^getmsg_")) 
async def send_file_handler(client, callback):
    """Handles the initial inline button click from the group/channel."""
    
    user_id = callback.from_user.id
    message_id_str = callback.data.split("_")[1]
    message_id = int(message_id_str)
    
    is_admin = user_id in ADMINS
    
    # 1. ADMIN CHECK
    if is_admin:
        await callback.answer("Admin. Copying file...", show_alert=False)
        # File sending handles deletion upon success. No immediate deletion here.
        await handle_send_file(
            client, 
            user_id, 
            message_id, 
            delete_message_id=callback.message.id, 
            delete_chat_id=callback.message.chat.id
        )
        return
        
    # 2. FORCE SUB CHECK
    if FORCE_SUB_CHANNEL and not await is_subscribed(client, user_id, max_retries=3):
        # Mixed Malayalam/English for button clarity
        join_button = [
            [InlineKeyboardButton("✅ Join Channel", url=f"https://t.me/{FORCE_SUB_CHANNEL.replace('@', '')}")],
            [InlineKeyboardButton("👍 Joined, Send File", callback_data=f"checksub_{message_id}_{callback.message.id}_{callback.message.chat.id}")] 
        ]
        
        # Force sub messages
        await callback.answer("✋ To get the file, join the channel. More details have been sent to your DM.", show_alert=True)
        try:
            # Send the ISOLATED Force Sub message to DM
            await client.send_message(
                chat_id=user_id,
                text=(
                    "🔑 **Mandatory Step!** 🔑\n\n"
                    f"To receive the file you requested, you must join our channel, {FORCE_SUB_CHANNEL}. "
                    "After joining, please click the button below.\n\n"
                    "**Remember:** You must have sent **/start** in this chat to receive the file."
                ),
                reply_markup=InlineKeyboardMarkup(join_button)
            )
            await callback.answer("Click the button that appeared in your Private Chat (DM).", show_alert=True)
        except Exception as e:
            print(f"Error sending force sub message to user {user_id}: {e}")
            await callback.answer("❌ Failed to send file! First send **/start** in DM, then try again.", show_alert=True)
        return 

    # 3. SUBSCRIBED / NO FORCE SUB: Direct send
    await callback.answer("Sending file to DM...", show_alert=False)
    success, result_message = await handle_send_file(
        client, 
        user_id, 
        message_id, 
        # Delete the search message upon successful file delivery
        delete_message_id=callback.message.id, 
        delete_chat_id=callback.message.chat.id
    )
    
    if success:
        await callback.answer("File received in your DM.", show_alert=False)
    else:
        # Error message is already sent to the user inside handle_send_file
        pass

            
# --- NEW CALLBACK HANDLER FOR FORCE SUB CHECK IN DM ---
@app.on_callback_query(filters.regex("^checksub_")) 
async def check_sub_handler(client, callback):
    """Handles the 'Check Subscription and Send File' button in the private chat."""
    
    user_id = callback.from_user.id
    
    # Data is split into: [checksub, message_id, group_message_id, group_chat_id]
    data_parts = callback.data.split("_")
    message_id = int(data_parts[1])
    group_message_id = int(data_parts[2])
    group_chat_id = int(data_parts[3])

    # Re-check subscription
    if FORCE_SUB_CHANNEL and not await is_subscribed(client, user_id, max_retries=2): 
        await callback.answer("❌ You have not joined the channel. Please try again.", show_alert=True)
        return
    
    # Subscription SUCCESS: Now send the file (reusing core logic)
    await callback.answer("✅ Subscription confirmed. Sending file...", show_alert=False)
    
    success, result_message = await handle_send_file(
        client, 
        user_id, 
        message_id, 
        # Delete the search message upon successful file delivery
        delete_message_id=group_message_id, 
        delete_chat_id=group_chat_id
    )
    
    if success:
        # Edit the original "Join Channel" message to say success in DM
        await callback.message.edit_text("✅ Subscription confirmed. File will be sent soon!")
    else:
        # If handle_send_file failed, it has already sent an error message to the user.
        await callback.message.edit_text(f"❌ An error occurred while sending the file.")


# --- MAIN ENTRY POINT ---

if __name__ == "__main__":
    if WEBHOOK_URL_BASE:
        # Use uvicorn to serve the FastAPI app (for Render deployment)
        uvicorn.run("main:api_app", host="0.0.0.0", port=PORT, log_level="info")
    else:
        # Use app.run() for local polling mode testing
        print("Starting Pyrogram in polling mode...")
        asyncio.run(startup_initial_checks())
        app.run()

