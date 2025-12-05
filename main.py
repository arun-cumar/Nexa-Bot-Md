Import os
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
from fastapi import FastAPI, Request, Response # Important: Imports needed for Uvicorn
from contextlib import asynccontextmanager
from http import HTTPStatus
import uvicorn

# Load variables from the .env file
load_dotenv()

# --- GLOBAL STATUS FLAG ---
IS_INDEXING_RUNNING = False

# --- CONFIG VARIABLES ---
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
PRIVATE_FILE_STORE = int(os.environ.get("PRIVATE_FILE_STORE", -100)) # Channel ID where files are stored
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", -100))
USER_SESSION_STRING = os.environ.get("USER_SESSION_STRING", None) 

# Admin list
ADMINS = []
admin_env = os.environ.get("ADMINS", "")
if admin_env:
    ADMINS = [int(admin.strip()) for admin in admin_env.split(',') if admin.strip().isdigit()]

DATABASE_URL = os.environ.get("DATABASE_URL", "mongodb://localhost:27017")
FORCE_SUB_CHANNEL = os.environ.get("FORCE_SUB_CHANNEL", None) # Force subscribe channel (e.g., @MyChannel)

# Webhook details
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

    async def find_one(self, query: Dict[str, Any]) -> Dict[str, Any] | None:
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
user_client: Client | None = None
if USER_SESSION_STRING:
    user_client = Client(
        "indexer_session",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=USER_SESSION_STRING, 
    )
    print("User session initialized for indexing/forwarding.")


# --- RENDER WEBHOOK SETUP (FastAPI) - MOVED UP TO PREVENT LOADING ERRORS ---

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
def get_file_info(message: Message) -> tuple[str, str, Union[Document, Video, Audio, None]]:
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

# --- START COMMAND (Malayalam Conversational) ---
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    """Handles the /start command in a private chat."""
    global IS_INDEXING_RUNNING
    
    if IS_INDEXING_RUNNING:
        await message.reply_text("ഇൻഡെക്സിംഗ് ഇപ്പോൾ നടന്നുകൊണ്ടിരിക്കുകയാണ്. ഇത് പൂർത്തിയാകും വരെ ദയവായി കാത്തിരിക്കുക.")
        return
        
    # Malayalam conversational start message
    start_text = (
        "ഹായ്! ഞാനാണ് നിങ്ങളുടെ **ഓട്ടോ ഫിൽട്ടർ ബോട്ട്.** 🤩\n\n"
        "🔎 **എന്നെ എങ്ങനെ ഉപയോഗിക്കാം?**\n"
        "1. ഞാൻ അഡ്മിനായുള്ള ഏതെങ്കിലും ഗ്രൂപ്പിലോ ചാനലിലോ നിങ്ങൾക്കാവശ്യമുള്ള സിനിമയുടെയോ സീരീസിൻ്റെയോ പേര് ടൈപ്പ് ചെയ്യുക.\n"
        "2. അവിടെ വരുന്ന റിസൾട്ട് ബട്ടണിൽ ക്ലിക്ക് ചെയ്യുക.\n"
        "3. ഫയൽ ഉടൻ നിങ്ങളുടെ ഈ പ്രൈവറ്റ് ചാറ്റിലേക്ക് (DM) അയച്ചുതരും! 🎉\n\n"
        "⚠️ **ശ്രദ്ധിക്കുക:** ഫയലുകൾ ലഭിക്കാൻ, ആദ്യം നിങ്ങൾ ഈ പ്രൈവറ്റ് ചാറ്റിൽ **/start** അയച്ച് എന്നോട് സംസാരിക്കണം. അതിനുശേഷം ഗ്രൂപ്പിലെ ബട്ടൺ ക്ലിക്കുചെയ്യുക.\n\n"
        "🔗 **ഞങ്ങളുടെ ചാനലുകൾ:**\n"
        "°•➤ @Mala_Television\n"
        "°•➤ @Mala_Tv\n"
        "°•➤ @MalaTvbot ™️\n\n"
        "**അഡ്മിൻ കമാൻഡുകൾ (Admin Commands):**\n"
        "• `/index` - ചാനലിലെ എല്ലാ ഫയലുകളും ഇൻഡെക്സ് ചെയ്യാൻ.\n"
        "• `/dbcount` - ഡാറ്റാബേസിലെ ഫയലുകളുടെ എണ്ണം പരിശോധിക്കാൻ."
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
        await message.reply_text("❌ ശ്രദ്ധിക്കുക: ഇൻഡെക്സിംഗ് പ്രോസസ്സ് നിലവിൽ നടന്നുകൊണ്ടിരിക്കുകയാണ്. ഇത് പൂർത്തിയാകും വരെ കാത്തിരിക്കുക.")
        return

    if PRIVATE_FILE_STORE == -100:
        await message.reply_text("PRIVATE_FILE_STORE ID ENV-യിൽ നൽകിയിട്ടില്ല. ഇൻഡെക്സിംഗ് സാധ്യമല്ല.")
        return
    
    if not USER_SESSION_STRING or not user_client:
         await message.reply_text("❌ ഇൻഡെക്സിംഗ് പിശക്: **USER_SESSION_STRING** നൽകിയിട്ടില്ല. ദയവായി യൂസർ സെഷൻ സ്ട്രിംഗ് നൽകുക.")
         return

    IS_INDEXING_RUNNING = True 
    
    msg = await message.reply_text("🔑 യൂസർ സെഷൻ ഉപയോഗിച്ച് ഫയൽ ഇൻഡെക്സിംഗ് ആരംഭിക്കുന്നു... ഇത് കുറച്ച് സമയമെടുത്തേക്കാം. (ലോഗുകൾ പരിശോധിക്കുക)")
    
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
                             await msg.edit_text(f"✅ ഇൻഡെക്സ് ചെയ്ത ഫയലുകൾ: {total_files_indexed} / {total_messages_processed}")
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
        await msg.edit_text(f"🎉 ഇൻഡെക്സിംഗ് പൂർത്തിയായി! ആകെ {total_files_indexed} ഫയലുകൾ ചേർക്കുകയോ അപ്ഡേറ്റ് ചെയ്യുകയോ ചെയ്തു. ({total_messages_processed} മെസ്സേജുകൾ പരിശോധിച്ചു)")
        
    except Exception as general_error:
        await msg.edit_text(f"❌ ഇൻഡെക്സിംഗ് പിശക്: {general_error}. യൂസർ അക്കൗണ്ടിന് ചാനലിലേക്ക് പ്രവേശനമുണ്ടോ എന്നും ID ശരിയാണോ എന്നും പരിശോധിക്കുക.")
        
    finally:
        # Do not stop user_client here if it's needed for forwarding
        IS_INDEXING_RUNNING = False

@app.on_message(filters.command("dbcount") & filters.user(ADMINS))
async def dbcount_command(client, message: Message):
    """Command to check the total number of files in the database."""
    try:
        count = await db.files_col.count_documents({})
        await message.reply_text(f"📊 **ഡാറ്റാബേസ് കൗണ്ട്:**\nആകെ ഇൻഡെക്സ് ചെയ്ത ഫയലുകൾ: **{count}**")
    except Exception as e:
        await message.reply_text(f"❌ ഡാറ്റാബേസ് കൗണ്ട് എടുക്കുന്നതിൽ പിശക്: {e}")

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
            await message.reply_text("ഇൻഡെക്സിംഗ് നടന്നുകൊണ്ടിരിക്കുകയാണ്. ദയവായി പ്രോസസ്സ് പൂർത്തിയാകുമ്പോൾ വീണ്ടും ശ്രമിക്കുക.")
        return
    
    # --- 1. COPYRIGHT MESSAGE DELETION LOGIC ---
    COPYRIGHT_KEYWORDS = ["copyright", "unauthorized", "DMCA", "piracy"] 
    is_copyright_message = any(keyword.lower() in query.lower() for keyword in COPYRIGHT_KEYWORDS)
    is_protected_chat = chat_id == PRIVATE_FILE_STORE or chat_id in ADMINS
    
    if is_copyright_message and is_protected_chat:
        try:
            await message.delete()
            # Log the deletion
            await client.send_message(LOG_CHANNEL, f"🚫 **പകർപ്പവകാശ സന്ദേശം നീക്കം ചെയ്തു!**\n\n**Chat ID:** `{chat_id}`\n**User:** {message.from_user.mention}\n**Message:** `{query}`")
            return
        except Exception as e:
            print(f"Error deleting copyright message in chat {chat_id}: {e}")
            return
            
    # --- 2. AUTO-FILTER SEARCH (ONLY IN GROUPS/CHANNELS) ---
    
    if chat_type == ChatType.PRIVATE:
        # Malayalam instruction for private chat search
        await message.reply_text("👋 ഫയലുകൾ തിരയാനായി, ദയവായി ഞാൻ അഡ്മിനായുള്ള ഒരു ഗ്രൂപ്പിലോ ചാനലിലോ പോയി പേര് ടൈപ്പ് ചെയ്യുക. അവിടെ വരുന്ന ബട്ടൺ ക്ലിക്ക് ചെയ്താൽ ഫയൽ ഇവിടെ ലഭിക്കും.")
        return
        
    if chat_id == PRIVATE_FILE_STORE:
        return
        
    # --- SEARCH IN GROUPS AND CHANNELS ---
    
    files = await get_file_details(query)
    
    if files:
        # Files found: Send inline buttons (Malayalam)
        text = f"✅ **{query} എന്നതിനായുള്ള റിസൾട്ടുകൾ:**\n\nഫയൽ ലഭിക്കാൻ താഴെയുള്ള ബട്ടണിൽ ക്ലിക്ക് ചെയ്യുക. ഫയൽ നിങ്ങളുടെ പ്രൈവറ്റ് ചാറ്റിലേക്ക് (DM) അയച്ചുതരും."
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
             buttons.append([InlineKeyboardButton("കൂടുതൽ റിസൾട്ടുകൾ ➡️", url="https://t.me/your_search_group")]) 

        sent_message = await message.reply_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
        
        # --- AUTODELETE LOGIC (after 60 seconds) ---
        await asyncio.sleep(60)
        try:
            await sent_message.delete()
        except Exception as e:
            print(f"Error during autodelete: {e}")
    else:
        # Optional: Reply if nothing found to indicate the search completed (Malayalam)
        # await message.reply_text(f"❌ ക്ഷമിക്കണം, '{query}' എന്ന പേരിൽ ഫയലുകളൊന്നും കണ്ടെത്താനായില്ല.", quote=True)
        pass
                
# --- CALLBACK QUERY HANDLER (INLINE BUTTON CLICK) ---

async def handle_send_file(client, user_id, message_id, delete_message_id=None, delete_chat_id=None):
    """
    Core function to copy/forward the file content with fallback.
    """
    
    file = await db.files_col.find_one({"message_id": message_id}) 
    
    if not file:
        # Ensure error message is sent immediately if file not found (Malayalam)
        try:
            await client.send_message(user_id, "❌ ക്ഷമിക്കണം, ഈ ഫയൽ ഡാറ്റാബേസിൽ നിന്ന് നീക്കം ചെയ്തിരിക്കുന്നു.")
        except Exception:
            pass
        return False, "File removed."

    # --- 1. Attempt to Copy the File (Bot client) ---
    try:
        await client.copy_message(
            chat_id=user_id, 
            from_chat_id=file['chat_id'],
            message_ids=file['message_id']
        )
        
        # Delete the original group filter message if needed
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
                     
                await user_client.forward_messages(
                    chat_id=user_id, 
                    from_chat_id=file['chat_id'], 
                    message_ids=file['message_id']
                )
                
                # Delete the original group filter message if needed
                if delete_message_id and delete_chat_id:
                    try:
                        await client.delete_messages(delete_chat_id, delete_message_id)
                    except Exception:
                        pass
                        
                return True, "File forwarded successfully via user session."
            except Exception as forward_e:
                print(f"Fallback forwarding failed for user {user_id}: {forward_e}")
                # Fallback failed, proceed to final error message
        
        # --- 3. Final Error Message (After all failures) (Malayalam) ---
        error_msg = ("❌ **ക്ഷമിക്കണം, ഫയൽ അയക്കാൻ കഴിഞ്ഞില്ല!** ❌\n\n"
                     "ഈ പ്രശ്നം പരിഹരിക്കാൻ ഈ കാര്യങ്ങൾ ശ്രദ്ധിക്കുക:\n"
                     "1. നിങ്ങൾ എന്നെ ബ്ലോക്ക് ചെയ്തിട്ടുണ്ടെങ്കിൽ, ഉടൻ അൺബ്ലോക്ക് ചെയ്ത ശേഷം **/start** വീണ്ടും അയക്കുക.\n"
                     "2. നിങ്ങളുടെ പ്രൈവറ്റ് ചാറ്റ് സെറ്റിംഗ്‌സിൽ ഫയലുകൾ ലഭിക്കാൻ അനുമതി നൽകിയിട്ടുണ്ടോയെന്ന് പരിശോധിക്കുക.\n\n"
                     "ദയവായി **/start** അയച്ച് വീണ്ടും ശ്രമിക്കുക.")
        try:
            await client.send_message(user_id, error_msg)
        except Exception:
            pass # Cannot send error message if user blocked the bot
            
        return False, error_msg
        
    except Exception as e:
        print(f"Unexpected error copying file to user {user_id}: {e}")
        error_msg = "❌ ഫയൽ അയക്കുന്നതിൽ ഒരു അപ്രതീക്ഷിത പിശക് സംഭവിച്ചു. (Failed to copy file)"
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
        await callback.answer("അഡ്മിൻ. ഫയൽ കോപ്പി ചെയ്യുന്നു...", show_alert=False)
        await handle_send_file(client, user_id, message_id)
        try:
             # Delete the inline search message for admins immediately
            await callback.message.delete()
        except Exception:
            pass 
        return
        
    # 2. FORCE SUB CHECK
    if FORCE_SUB_CHANNEL and not await is_subscribed(client, user_id, max_retries=3):
        # Mixed Malayalam/English for button clarity
        join_button = [
            [InlineKeyboardButton("✅ Join Channel", url=f"https://t.me/{FORCE_SUB_CHANNEL.replace('@', '')}")],
            [InlineKeyboardButton("👍 Joined, Send File", callback_data=f"checksub_{message_id}_{callback.message.id}_{callback.message.chat.id}")] 
        ]
        
        # Malayalam force sub messages
        await callback.answer("✋ ഫയൽ ലഭിക്കാൻ ചാനലിൽ ജോയിൻ ചെയ്യുക. കൂടുതൽ വിവരങ്ങൾ DM-ൽ നൽകിയിട്ടുണ്ട്.", show_alert=True)
        try:
            # Send the ISOLATED Force Sub message to DM
            await client.send_message(
                chat_id=user_id,
                text=(
                    "🔑 **നിർബന്ധമായും ചെയ്യേണ്ട ഒരു കാര്യം!** 🔑\n\n"
                    f"നിങ്ങൾക്കാവശ്യമുള്ള ഫയൽ ലഭിക്കാൻ, ഞങ്ങളുടെ ചാനലായ {FORCE_SUB_CHANNEL} -ൽ ജോയിൻ ചെയ്യണം. "
                    "ജോയിൻ ചെയ്ത ശേഷം താഴെയുള്ള ബട്ടണിൽ ക്ലിക്ക് ചെയ്യുക.\n\n"
                    "**ഓർക്കുക:** ഫയൽ ലഭിക്കാൻ ഈ ചാറ്റിൽ **/start** അയച്ച് എന്നോട് സംസാരിച്ചിരിക്കണം."
                ),
                reply_markup=InlineKeyboardMarkup(join_button)
            )
            await callback.answer("നിങ്ങളുടെ പ്രൈവറ്റ് ചാറ്റിൽ (DM) വന്ന ബട്ടൺ ക്ലിക്കുചെയ്യുക.", show_alert=True)
        except Exception as e:
            print(f"Error sending force sub message to user {user_id}: {e}")
            await callback.answer("❌ ഫയൽ അയക്കാൻ കഴിഞ്ഞില്ല! ആദ്യം **/start** അയച്ച് DM-ൽ വരിക, എന്നിട്ട് വീണ്ടും ശ്രമിക്കുക.", show_alert=True)
        return 

    # 3. SUBSCRIBED / NO FORCE SUB: Direct send
    await callback.answer("ഫയൽ DM-ലേക്ക് അയക്കുന്നു...", show_alert=False)
    success, result_message = await handle_send_file(
        client, 
        user_id, 
        message_id, 
        delete_message_id=callback.message.id, 
        delete_chat_id=callback.message.chat.id
    )
    
    if success:
        await callback.answer("ഫയൽ നിങ്ങളുടെ DM-ൽ ലഭിച്ചു.", show_alert=False)
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
        await callback.answer("❌ നിങ്ങൾ ചാനലിൽ ജോയിൻ ചെയ്തിട്ടില്ല. ദയവായി വീണ്ടും ശ്രമിക്കുക.", show_alert=True)
        return
    
    # Subscription SUCCESS: Now send the file (reusing core logic)
    await callback.answer("✅ സബ്സ്ക്രിപ്ഷൻ സ്ഥിരീകരിച്ചു. ഫയൽ അയക്കുന്നു...", show_alert=False)
    
    success, result_message = await handle_send_file(
        client, 
        user_id, 
        message_id, 
        delete_message_id=group_message_id, 
        delete_chat_id=group_chat_id
    )
    
    if success:
        # Edit the original "Join Channel" message to say success in DM (Malayalam)
        await callback.message.edit_text("✅ സബ്സ്ക്രിപ്ഷൻ സ്ഥിരീകരിച്ചു. ഫയൽ ഉടൻ അയച്ചുതരും!")
    else:
        # If handle_send_file failed, it has already sent an error message to the user.
        await callback.message.edit_text(f"❌ ഫയൽ അയക്കുന്നതിൽ ഒരു പിശക് സംഭവിച്ചു.")


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

