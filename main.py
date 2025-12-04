import os
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import MessagesFilter, ChatType
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, Document, Video, Audio
from pyrogram.errors import UserNotParticipant, MessageNotModified
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from typing import List, Dict, Any, Union
from fastapi import FastAPI, Request, Response
from contextlib import asynccontextmanager
from http import HTTPStatus
import uvicorn

# .env ഫയലിൽ നിന്നുള്ള വേരിയബിളുകൾ ലോഡ് ചെയ്യുന്നു
load_dotenv()

# --- ഗ്ലോബൽ സ്റ്റാറ്റസ് ഫ്ലാഗ് ---
# ഇൻഡെക്സിംഗ് നടക്കുന്നുണ്ടോ എന്ന് ട്രാക്ക് ചെയ്യുന്നു.
IS_INDEXING_RUNNING = False

# --- കോൺഫിഗ് വേരിയബിളുകൾ ---
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
PRIVATE_FILE_STORE = int(os.environ.get("PRIVATE_FILE_STORE", -100)) # ഫയലുകൾ സ്റ്റോർ ചെയ്തിട്ടുള്ള ചാനൽ ഐഡി
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", -100))
# പ്രൈവറ്റ് ചാനൽ ഇൻഡെക്സ് ചെയ്യാൻ യൂസർ സെഷൻ സ്ട്രിംഗ് നിർബന്ധമാണ്
USER_SESSION_STRING = os.environ.get("USER_SESSION_STRING", None) 


# അഡ്മിൻ ലിസ്റ്റ്
ADMINS = []
admin_env = os.environ.get("ADMINS", "")
if admin_env:
    ADMINS = [int(admin.strip()) for admin in admin_env.split(',') if admin.strip().isdigit()]

DATABASE_URL = os.environ.get("DATABASE_URL", "mongodb://localhost:27017")
FORCE_SUB_CHANNEL = os.environ.get("FORCE_SUB_CHANNEL", None) # ഫോഴ്സ് സബ് ചാനൽ (ഉദാഹരണത്തിന് @MyChannel)

# വെബ്ഹുക്ക് വിശദാംശങ്ങൾ
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL_BASE", None)
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_PATH = f"/{BOT_TOKEN}"

# --- മോങ്കോഡിബി സജ്ജീകരണം ---

class Database:
    """Handles database operations."""
    def __init__(self, uri: str, database_name: str):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.files_col = self.db["files"]

    async def get_all_files(self) -> List[Dict[str, Any]]:
        """എല്ലാ ഫയൽ എൻട്രികളും ലിസ്റ്റായി തിരികെ നൽകുന്നു."""
        cursor = self.files_col.find({})
        return await cursor.to_list(length=None)

    async def find_one(self, query: Dict[str, Any]) -> Dict[str, Any] | None:
        return await self.files_col.find_one(query)

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        await self.files_col.update_one(query, update, upsert=upsert)

# ഡാറ്റാബേസ് ഇൻസ്റ്റൻസ്
db = Database(DATABASE_URL, "AutoFilterBot")

# --- പൈറോഗ്രാം ക്ലൈന്റ് ---
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

# --- ബോട്ട് ഇൻസ്റ്റൻസ് (ഗ്ലോബൽ പൈറോഗ്രാം ക്ലൈന്റ്) ---
app = AutoFilterBot()

# --- സഹായികൾ ---

async def is_subscribed(client, user_id):
    """ഫോഴ്സ് സബ്സ്ക്രൈബ് ചാനലിൽ യൂസർ അംഗമാണോ എന്ന് പരിശോധിക്കുന്നു."""
    if not FORCE_SUB_CHANNEL:
        return True
    try:
        # ബോട്ടിൽ യൂസർ ചാനലിൽ ഉണ്ടോ എന്ന് പരിശോധിക്കുന്നു
        member = await client.get_chat_member(FORCE_SUB_CHANNEL, user_id) 
        if member.status in ["member", "administrator", "creator"]:
            return True
        return False
    except UserNotParticipant:
        print("DEBUG: യൂസർ ഫോഴ്സ് സബ് ചാനലിൽ അംഗമല്ല.")
        return False
    except Exception as e:
        print(f"സബ്സ്ക്രിപ്ഷൻ പരിശോധിക്കുന്നതിൽ പിശക്: {e}")
        return True 

async def get_file_details(query):
    """മെച്ചപ്പെടുത്തിയ റെഗുലർ എക്സ്പ്രഷൻ ഉപയോഗിച്ച് ഫയൽ വിവരങ്ങൾ ഡാറ്റാബേസിൽ തിരയുന്നു."""
    
    print(f"DEBUG: തിരയുന്ന വാക്ക്: '{query}'")

    # തിരയൽ വാചകത്തിലെ പ്രത്യേക ചിഹ്നങ്ങൾ കൈകാര്യം ചെയ്യുന്നു 
    escaped_query = re.escape(query)
    
    # ടൈറ്റിലിൻ്റെയോ ക്യാപ്ഷൻ്റെയോ ഏത് ഭാഗത്ത് വേണമെങ്കിലും തിരയാൻ സഹായിക്കുന്ന റെഗുലർ എക്സ്പ്രഷൻ
    regex_pattern = f".*{escaped_query}.*"
    
    # ടൈറ്റിലിലോ ക്യാപ്ഷനിലോ കേസ്-ഇൻസെൻസിറ്റീവായി ഭാഗികമായി പൊരുത്തപ്പെടുത്താൻ $regex ഉപയോഗിക്കുന്നു
    cursor = db.files_col.find({ 
        "$or": [
            {"title": {"$regex": regex_pattern, "$options": "i"}},
            {"caption": {"$regex": regex_pattern, "$options": "i"}}
        ]
    }).limit(10)
    
    files = await cursor.to_list(length=10)
    
    print(f"DEBUG: '{query}' എന്ന വാക്കിന് {len(files)} ഫയലുകൾ കണ്ടെത്തി")
    
    return files

# ഫയൽ വിവരങ്ങൾ വേർതിരിച്ചെടുക്കുന്ന ഫംഗ്ഷൻ
def get_file_info(message: Message) -> tuple[str, str, Union[Document, Video, Audio, None]]:
    """ഒരു സന്ദേശത്തിൽ നിന്ന് file_id, file_name, file_object എന്നിവ കണ്ടെത്തുന്നു."""
    if message.document and message.document.file_name:
        return message.document.file_id, message.document.file_name, message.document
    if message.video:
        file_name = message.caption.strip() if message.caption else f"Video_{message.id}"
        return message.video.file_id, file_name, message.video
    if message.audio:
        file_name = message.audio.file_name or message.audio.title or f"Audio_{message.id}"
        return message.audio.file_id, file_name, message.audio
    return None, None, None

# --- START COMMAND ---
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    """Handles the /start command in a private chat with custom text."""
    global IS_INDEXING_RUNNING
    
    if IS_INDEXING_RUNNING:
        await message.reply_text("ഇൻഡെക്സിംഗ് നടന്നുകൊണ്ടിരിക്കുകയാണ്. അത് പൂർത്തിയാകുന്നതുവരെ ദയവായി കാത്തിരിക്കുക.")
        return
        
    # User's customized start message
    await message.reply_text(
        "**𝚒'𝚖 𝚊𝚗 𝚊𝚍𝚟𝚊𝚗𝚌𝚎𝚍 𝚖𝚘𝚟𝚒𝚎𝚜 & 𝚜𝚎𝚛𝚒𝚎𝚜 𝚜𝚎𝚊𝚛𝚌𝚑 𝚋𝚘𝚝 & 𝚖𝚘𝚛𝚎 𝚏𝚎𝚊𝚝𝚞𝚛𝚎𝚜.!❤️**\n"
        "°•➤@Mala_Television🍿  \n"
        "°•➤@Mala_Tv \n"
        "°•➤@MalaTvbot  ™️\n"
        "🙂🙂\n\n"
        "ഞാൻ അഡ്മിനായ ഗ്രൂപ്പിലോ ചാനലിലോ വന്ന് സിനിമയുടെ പേര് ടൈപ്പ് ചെയ്യുക. റിസൾട്ട് ലഭിക്കുമ്പോൾ ബട്ടൺ ക്ലിക്കുചെയ്താൽ ഫയൽ ഇവിടെ സ്വകാര്യമായി അയച്ചുതരും.\n\n"
        "**Admin Commands:**\n"
        "• `/index` - ചാനലിലെ എല്ലാ ഫയലുകളും ഇൻഡെക്സ് ചെയ്യാൻ.\n"
        "• `/dbcount` - ഡാറ്റാബേസിലെ ഫയലുകളുടെ എണ്ണം പരിശോധിക്കാൻ."
    )
    print(f"DEBUG: {message.from_user.id} എന്ന ഐഡിയിൽ നിന്ന് സ്റ്റാർട്ട് കമാൻഡ് ലഭിച്ചു")

@app.on_message(filters.command("index") & filters.user(ADMINS))
async def index_command(client, message: Message):
    """
    Command to index all files from the file store channel using the user session.
    """
    global IS_INDEXING_RUNNING
    
    if IS_INDEXING_RUNNING:
        await message.reply_text("❌ മുന്നറിയിപ്പ്: ഇൻഡെക്സിംഗ് പ്രോസസ്സ് നിലവിൽ പ്രവർത്തിക്കുന്നു. ഇപ്പോഴത്തെ ജോലി പൂർത്തിയാക്കാൻ കാത്തിരിക്കുക.")
        return

    if PRIVATE_FILE_STORE == -100:
        await message.reply_text("PRIVATE_FILE_STORE ID ENV-യിൽ നൽകിയിട്ടില്ല. ഇൻഡെക്സിംഗ് സാധ്യമല്ല.")
        return
    
    if not USER_SESSION_STRING:
         await message.reply_text("❌ ഇൻഡെക്സിംഗ് പിശക്: **USER_SESSION_STRING** ENV-യിൽ നൽകിയിട്ടില്ല. യൂസർ സെഷൻ സ്ട്രിംഗ് ഉണ്ടാക്കി നൽകുക.")
         return

    IS_INDEXING_RUNNING = True # Set flag to True
    
    msg = await message.reply_text("🔑 യൂസർ സെഷൻ ഉപയോഗിച്ച് പൂർണ്ണമായ ഓട്ടോമാറ്റിക് ഫയൽ ഇൻഡെക്സിംഗ് ആരംഭിക്കുന്നു... ഇതിന് സമയമെടുത്തേക്കാം. (ലോഗുകൾ പരിശോധിക്കുക)")
    
    total_files_indexed = 0
    total_messages_processed = 0
    
    # --- INITIALIZE USER CLIENT FOR INDEXING ---
    user_client = Client(
        "indexer_session",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=USER_SESSION_STRING, # Logs in as user account
    )

    try:
        await user_client.start() # Starts the user client

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
                         # Update status after every 50 files
                         try:
                             await msg.edit_text(f"✅ ഇൻഡെക്സ് ചെയ്ത ഫയലുകൾ: {total_files_indexed} / {total_messages_processed}")
                             print(f"INDEX_DEBUG: {file_name} വിജയകരമായി ഇൻഡെക്സ് ചെയ്തു") 
                         except MessageNotModified:
                             pass # Ignore if text is the same.

                except Exception as db_error:
                    print(f"INDEX_DEBUG: {file_name} എന്ന ഫയലിനുള്ള DB WRITE പിശക്: {db_error}")
            else:
                if chat_msg.text:
                    print(f"INDEX_DEBUG: ടെക്സ്റ്റ് മെസ്സേജ് {chat_msg.id} ഒഴിവാക്കുന്നു")
                else:
                    print(f"INDEX_DEBUG: മെസ്സേജ് {chat_msg.id} ഒഴിവാക്കുന്നു - പിന്തുണയ്ക്കുന്ന ഫയൽ തരം (Doc/Vid/Aud) അല്ല.")
            
        # Final report after indexing is complete
        await msg.edit_text(f"🎉 ഇൻഡെക്സിംഗ് പൂർത്തിയായി! ആകെ {total_files_indexed} ഫയലുകൾ ചേർക്കുകയോ അപ്ഡേറ്റ് ചെയ്യുകയോ ചെയ്തു. ({total_messages_processed} സന്ദേശങ്ങൾ പ്രോസസ്സ് ചെയ്തു)")
        
    except Exception as general_error:
        # Catch major errors like lack of channel access
        await msg.edit_text(f"❌ ഇൻഡെക്സിംഗ് പിശക്: {general_error}. യൂസർ അക്കൗണ്ടിന് ചാനലിലേക്ക് ആക്സസ് ഉണ്ടോ എന്നും ഐഡി ശരിയാണോ എന്നും പരിശോധിക്കുക.")
        print(f"INDEX_DEBUG: മാരകമായ ഇൻഡെക്സിംഗ് പിശക്: {general_error}")
        
    finally:
        await user_client.stop() # Stops the user client
        IS_INDEXING_RUNNING = False # Set flag to False

@app.on_message(filters.command("dbcount") & filters.user(ADMINS))
async def dbcount_command(client, message: Message):
    """Command to check the total number of files in the database."""
    try:
        count = await db.files_col.count_documents({})
        await message.reply_text(f"📊 **ഡാറ്റാബേസ് ഫയൽ കൗണ്ട്:**\nനിലവിൽ ഇൻഡെക്സ് ചെയ്ത ആകെ ഫയലുകൾ: **{count}**")
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
        await message.reply_text("ഇൻഡെക്സിംഗ് നടന്നുകൊണ്ടിരിക്കുകയാണ്. പ്രോസസ്സ് പൂർത്തിയാകുമ്പോൾ വീണ്ടും ശ്രമിക്കുക.")
        return
    
    print(f"DEBUG: Message received from chat {chat_id}: '{query}'")
    
    # --- 1. COPYRIGHT MESSAGE DELETION LOGIC ---
    COPYRIGHT_KEYWORDS = ["copyright", "unauthorized", "DMCA", "piracy"] 
    
    is_copyright_message = any(keyword.lower() in query.lower() for keyword in COPYRIGHT_KEYWORDS)
    is_protected_chat = chat_id == PRIVATE_FILE_STORE or chat_id in ADMINS
    
    if is_copyright_message and is_protected_chat:
        try:
            await message.delete()
            # Log the deletion
            await client.send_message(LOG_CHANNEL, f"🚫 **Copyright Message Deleted!**\n\n**Chat ID:** `{chat_id}`\n**User:** {message.from_user.mention}\n**Message:** `{query}`")
            return
        except Exception as e:
            print(f"Error deleting copyright message in chat {chat_id}: {e}")
            return
    
    print("DEBUG: Copyright check passed. Proceeding to filter.")
            
    # --- 2. AUTO-FILTER SEARCH (ONLY IN GROUPS/CHANNELS) ---
    
    # Skip filtering in private chats (DM)
    if chat_type == ChatType.PRIVATE:
        await message.reply_text("👋 ഫയലുകൾ തിരയുന്നതിന് എന്നെ അഡ്മിനായി ചേർത്ത **ഗ്രൂപ്പിലോ ചാനലിലോ** പേര് ടൈപ്പ് ചെയ്യുക. അവിടെ ബട്ടൺ ക്ലിക്ക് ചെയ്താൽ ഞാൻ ഇവിടെ (ഈ DM-ൽ) ഫയൽ അയച്ചുതരും.")
        return
        
    # Skip messages from the file store channel
    if chat_id == PRIVATE_FILE_STORE:
        print("DEBUG: Message came from PRIVATE_FILE_STORE, skipping filter.")
        return
        
    # --- SEARCH IN GROUPS AND CHANNELS ---
    
    files = await get_file_details(query)
    
    if files:
        # Files found: Send inline buttons
        text = f"**{query}** യുമായി ബന്ധപ്പെട്ട ഫയലുകൾ ഇതാ:\n\nഫയൽ ലഭിക്കുന്നതിനായി ബട്ടൺ ക്ലിക്ക് ചെയ്യുക. ഫയൽ നിങ്ങളുടെ പ്രൈവറ്റ് ചാറ്റിൽ ലഭിക്കുന്നതാണ്."
        buttons = []
        for file in files:
            media_icon = {"document": "📄", "video": "🎬", "audio": "🎶"}.get(file.get('media_type', 'document'), '❓')
            # The file name saved during indexing will include the user's watermarks if present.
            file_name = file.get("title", "File").rsplit('.', 1)[0].strip() 
            
            buttons.append([
                InlineKeyboardButton(
                    text=f"{media_icon} {file_name}",
                    # Keep callback data short using message_id of the file
                    callback_data=f"getmsg_{file.get('message_id')}" 
                )
            ])
        
        if len(files) == 10:
             buttons.append([InlineKeyboardButton("കൂടുതൽ ഫലങ്ങൾ", url="https://t.me/your_search_group")]) 

        sent_message = await message.reply_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
        
        print(f"DEBUG: Sent filter results for search '{query}'. Starting autodelete timer.")
        
        # --- AUTODELETE LOGIC (after 60 seconds) ---
        await asyncio.sleep(60)
        try:
            await sent_message.delete()
            print("DEBUG: Autodelete complete.")
        except Exception as e:
            print(f"Error during autodelete: {e}")
            
                
# --- CALLBACK QUERY HANDLER (INLINE BUTTON CLICK) ---

@app.on_callback_query(filters.regex("^getmsg_")) 
async def send_file_handler(client, callback):
    """Sends the file privately when the inline button is clicked."""
    
    user_id = callback.from_user.id
    
    # Extract message_id from callback data
    message_id_str = callback.data.split("_")[1]
    message_id = int(message_id_str)
    
    # Force subscribe check
    if FORCE_SUB_CHANNEL and not await is_subscribed(client, user_id):
        # If the user has not subscribed, send a check button to DM
        join_button = [
            [InlineKeyboardButton("ചാനലിൽ അംഗമാകുക", url=f"https://t.me/{FORCE_SUB_CHANNEL.replace('@', '')}")],
            # NEW: Button to check subscription again immediately in DM
            [InlineKeyboardButton("✅ ജോയിൻ ചെയ്തു, ഫയൽ അയക്കുക", callback_data=f"checksub_{message_id}")] 
        ]
        
        await callback.answer("ഫയൽ ലഭിക്കാൻ ചാനലിൽ അംഗമാകുക. ജോയിൻ ചെയ്ത ശേഷം DM-ൽ വീണ്ടും ശ്രമിക്കുക.", show_alert=True)
        # Send a message in DM asking to subscribe
        try:
            await client.send_message(
                chat_id=user_id,
                text=f"നിങ്ങൾ ചാനലിൽ അംഗമായിട്ടില്ല. ദയവായി {FORCE_SUB_CHANNEL} എന്ന ചാനലിൽ ജോയിൻ ചെയ്യുക, എന്നിട്ട് താഴെയുള്ള ബട്ടൺ ക്ലിക്ക് ചെയ്യുക.",
                reply_markup=InlineKeyboardMarkup(join_button)
            )
        except Exception:
             # Cannot send message if user hasn't started the bot
             await callback.answer("ഫയൽ അയക്കുന്നതിൽ പിശക് സംഭവിച്ചു. ബോട്ടിൽ /start കമാൻഡ് അയച്ച് പ്രൈവറ്റ് ചാറ്റ് ആരംഭിക്കുക.", show_alert=True)
             return
        return

    # If subscribed, proceed to send the file
    
    # Find the file in the database using message_id
    file = await db.files_col.find_one({"message_id": message_id}) 
    
    if file:
        try:
            # Forward the file from the original store channel to the user's private chat
            await client.forward_messages(
                chat_id=user_id, # <-- User's private chat ID
                from_chat_id=file['chat_id'],
                message_ids=file['message_id']
            )
            # Send a confirmation message in the user's private chat
            await client.send_message(user_id, "✅ നിങ്ങൾ ആവശ്യപ്പെട്ട ഫയൽ ലഭിച്ചു.")
            
            await callback.answer("ഫയൽ നിങ്ങളുടെ പ്രൈവറ്റ് ചാറ്റിലേക്ക് അയച്ചിരിക്കുന്നു.", show_alert=True)
            
        except Exception as e:
            # If forwarding fails (e.g., user blocked the bot or hasn't started the bot)
            await callback.answer("ഫയൽ അയക്കുന്നതിൽ പിശക് സംഭവിച്ചു. ബോട്ടിൽ /start കമാൻഡ് അയച്ചോ എന്ന് പരിശോധിക്കുക.", show_alert=True)
            print(f"Error forwarding file to user {user_id}: {e}")
            
    else:
        await callback.answer("ഈ ഫയൽ ഡാറ്റാബേസിൽ നിന്ന് നീക്കം ചെയ്തിരിക്കുന്നു.", show_alert=True)
    
    # Delete the message in the group/channel
    try:
        await callback.message.delete()
    except Exception as e:
        print(f"Error deleting inline message: {e}")

# --- NEW CALLBACK HANDLER FOR FORCE SUB CHECK IN DM ---
@app.on_callback_query(filters.regex("^checksub_")) 
async def check_sub_handler(client, callback):
    """Handles the 'Check Subscription and Send File' button in the private chat."""
    
    user_id = callback.from_user.id
    
    # Extract message_id from callback data
    message_id_str = callback.data.split("_")[1]
    message_id = int(message_id_str)

    if FORCE_SUB_CHANNEL and not await is_subscribed(client, user_id):
        # Still not subscribed
        await callback.answer("❌ നിങ്ങൾ ഇതുവരെ ചാനലിൽ ജോയിൻ ചെയ്തിട്ടില്ല. വീണ്ടും ശ്രമിക്കുക.", show_alert=True)
        return
    
    # Subscription SUCCESS: Now send the file (reusing send logic)
    
    # Find the file in the database using message_id
    file = await db.files_col.find_one({"message_id": message_id}) 
    
    if file:
        try:
            # Forward the file from the original store channel to the user's private chat
            await client.forward_messages(
                chat_id=user_id, 
                from_chat_id=file['chat_id'],
                message_ids=file['message_id']
            )
            # Edit the original "Join Channel" message to say success
            await callback.message.edit_text("✅ ചാനലിൽ ജോയിൻ ചെയ്തു. ഫയൽ വിജയകരമായി അയച്ചിരിക്കുന്നു.")
            
            await callback.answer("ഫയൽ അയച്ചു.", show_alert=False)
            
        except Exception as e:
            await callback.answer("ഫയൽ അയക്കുന്നതിൽ പിശക് സംഭവിച്ചു. ബോട്ടിൽ /start കമാൻഡ് അയച്ചോ എന്ന് പരിശോധിക്കുക.", show_alert=True)
            print(f"Error forwarding file to user {user_id}: {e}")
    else:
        await callback.answer("ഈ ഫയൽ ഡാറ്റാബേസിൽ നിന്ന് നീക്കം ചെയ്തിരിക്കുന്നു.", show_alert=True)


# --- RENDER WEBHOOK SETUP (FastAPI) ---

# --- STARTUP/SHUTDOWN LIFECYCLE ---
async def startup_initial_checks():
    """Checks to run on startup."""
    print("Performing initial startup checks...")
    try:
        files_count = await db.files_col.count_documents({})
        print(f"Database check complete. Found {files_count} files in the database.")
    except Exception as e:
        print(f"WARNING: Database check failed on startup: {e}")


@asynccontextmanager
async def lifespan(web_app: FastAPI):
    await startup_initial_checks()
    
    if WEBHOOK_URL_BASE:
        await app.start() 
        await app.set_webhook(url=f"{WEBHOOK_URL_BASE}{WEBHOOK_PATH}")
        print(f"Webhook successfully set: {WEBHOOK_URL_BASE}{WEBHOOK_PATH}")
    else:
        await app.start()
        print("Starting in polling mode (for local testing only).")
        
    yield
    await app.stop()
    print("Application stopped.")

# FastAPI instance
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
