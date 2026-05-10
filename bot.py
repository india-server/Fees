import logging
import os
import re
from datetime import datetime
from dotenv import load_dotenv
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from bson import ObjectId

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, filters
)

# ================= CONFIG =================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_SECRET = os.getenv("OWNER_SECRET")
PORT = int(os.getenv("PORT", 10000))
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "peace_escrow_bot")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing in .env")
if not OWNER_SECRET:
    raise ValueError("OWNER_SECRET missing in .env")

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ================= MONGODB SETUP =================
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]

# Collections
channels_col = db["channels"]
admins_col = db["admins"]
broadcasts_col = db["broadcasts"]
users_col = db["users"]
settings_col = db["settings"]
fee_logs_col = db["fee_logs"]

# Create indexes
channels_col.create_index("number", unique=True)
admins_col.create_index("user_id", unique=True)
users_col.create_index("user_id", unique=True)
settings_col.create_index("key", unique=True)

# ================= WEB SERVER =================
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PEACE Escrow Bot – Status</title>
<style>
  *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    min-height: 100vh;
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Segoe UI', sans-serif; color: white;
  }
  .card {
    background: rgba(255,255,255,0.07);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255,255,255,0.13);
    border-radius: 28px;
    padding: 54px 64px;
    text-align: center;
    max-width: 520px; width: 92%;
    box-shadow: 0 32px 64px rgba(0,0,0,0.45);
  }
  .logo { font-size: 3.2rem; margin-bottom: 6px; }
  h1 { font-size: 2rem; margin-bottom: 4px; letter-spacing: 1px; }
  .sub { color: rgba(255,255,255,0.42); font-size: 0.88rem; margin-bottom: 32px; }
  .dot {
    width: 14px; height: 14px;
    background: #00ff88; border-radius: 50%;
    display: inline-block; margin-right: 8px;
    vertical-align: middle;
    animation: pulse 1.5s infinite;
  }
  @keyframes pulse {
    0%,100% { box-shadow: 0 0 0 0 rgba(0,255,136,0.5); }
    50% { box-shadow: 0 0 0 10px rgba(0,255,136,0); }
  }
  .badge {
    display: inline-block;
    background: rgba(0,255,136,0.12);
    border: 1px solid rgba(0,255,136,0.35);
    color: #00ff88;
    border-radius: 50px;
    padding: 10px 28px;
    font-size: 1rem; font-weight: 700;
    letter-spacing: 1px;
    margin-bottom: 32px;
  }
  .fee-table {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 20px 24px;
    text-align: left;
    margin-bottom: 28px;
  }
  .fee-table h3 {
    text-align: center; font-size: 1rem;
    color: #f0c040; margin-bottom: 14px; letter-spacing: 1px;
  }
  .fee-row {
    display: flex; justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    font-size: 0.87rem;
    color: rgba(255,255,255,0.8);
  }
  .fee-row:last-child { border-bottom: none; }
  .fee-row .charge { color: #00ff88; font-weight: 600; }
  .info { color: rgba(255,255,255,0.3); font-size: 0.8rem; line-height: 1.9; }
  .tag { color: #a78bfa; font-weight: 600; }
</style>
</head>
<body>
<div class="card">
  <div class="logo">🔐</div>
  <h1>PEACE Escrow Bot</h1>
  <p class="sub">Secure Middleman • Powered by python-telegram-bot</p>
  <div class="badge"><span class="dot"></span>ONLINE &amp; ACTIVE</div>
  <div class="fee-table">
    <h3>📊 FEE STRUCTURE</h3>
    <div class="fee-row"><span>Under ₹500</span><span class="charge">₹5 flat</span></div>
    <div class="fee-row"><span>₹501 – ₹1,000</span><span class="charge">₹10 flat</span></div>
    <div class="fee-row"><span>₹1,001 – ₹2,000</span><span class="charge">₹20 flat</span></div>
    <div class="fee-row"><span>₹2,001 – ₹3,000</span><span class="charge">2.5%</span></div>
    <div class="fee-row"><span>Above ₹3,000</span><span class="charge">2%</span></div>
  </div>
  <p class="info">
    All systems operational • Bot running smoothly<br>
    Use <strong>/p &lt;amount&gt;</strong> to calculate charges<br><br>
    <span class="tag">@PEACEESCROWSERVICE</span> &mdash; Safe • Secure • Trusted
  </p>
</div>
</body>
</html>"""

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode("utf-8"))
    def log_message(self, *args):
        pass

def run_web_server():
    HTTPServer(("0.0.0.0", PORT), WebHandler).serve_forever()

# ================= DATABASE OPERATIONS =================
def init_db():
    """Initialize MongoDB collections and indexes"""
    # Create indexes for better performance
    channels_col.create_index("number", unique=True)
    channels_col.create_index("active")
    admins_col.create_index("user_id", unique=True)
    admins_col.create_index("role")
    users_col.create_index("user_id", unique=True)
    users_col.create_index("first_seen")
    settings_col.create_index("key", unique=True)
    fee_logs_col.create_index("user_id")
    fee_logs_col.create_index("date")
    broadcasts_col.create_index("date")

# ================= HELPERS =================
def get_channels():
    """Get all active channels sorted by number"""
    return [(ch["number"], ch["link"]) for ch in channels_col.find(
        {"active": 1}
    ).sort("number", 1)]

def is_admin(uid: int) -> bool:
    """Check if user is admin or owner"""
    admin = admins_col.find_one({"user_id": uid})
    return admin is not None

def is_owner(uid: int) -> bool:
    """Check if user is owner"""
    admin = admins_col.find_one({"user_id": uid, "role": "owner"})
    return admin is not None

def get_owner():
    """Get owner user_id"""
    owner = admins_col.find_one({"role": "owner"})
    return owner["user_id"] if owner else None

def get_setting(key: str, default: str = "") -> str:
    """Get a setting value"""
    setting = settings_col.find_one({"key": key})
    return setting["value"] if setting else default

def set_setting(key: str, value: str):
    """Set a setting value"""
    settings_col.update_one(
        {"key": key},
        {"$set": {"value": value}},
        upsert=True
    )

def add_owner(uid: int):
    """Add owner to admins collection"""
    admins_col.update_one(
        {"user_id": uid},
        {"$set": {"role": "owner"}},
        upsert=True
    )

def save_user(uid: int):
    """Save user if not exists"""
    users_col.update_one(
        {"user_id": uid},
        {"$setOnInsert": {
            "user_id": uid,
            "first_seen": datetime.now().isoformat()
        }},
        upsert=True
    )

def build_channel_keyboard(channels, columns: int = 2):
    """Build inline keyboard for channels"""
    keyboard, row = [], []
    for n, l in channels:
        row.append(InlineKeyboardButton(f"𝐂𝐇𝐀𝐍𝐍𝐄𝐋 {n}", url=l))
        if len(row) == columns:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return keyboard

# ================= FEE CALCULATOR =================
def calculate_fee(amount: float) -> float:
    """Calculate escrow fee based on amount."""
    if amount <= 0:
        return 0.0
    elif amount < 500:
        return 5.0
    elif amount <= 1000:
        return 10.0
    elif amount <= 2000:
        return 20.0
    elif amount <= 3000:
        return round(amount * 0.025, 2)
    else:
        return round(amount * 0.02, 2)

def get_fee_slab(amount: float) -> str:
    """Return the fee slab description."""
    if amount <= 0:
        return "Invalid"
    elif amount < 500:
        return "• 𝐔𝐍𝐃𝐄𝐑 ₹𝟓𝟎𝟎           →  ₹𝟓 𝐅𝐋𝐀𝐓"
    elif amount <= 1000:
        return "• ₹𝟓𝟎𝟏 𝐓𝐎 ₹𝟏𝟎𝟎𝟎        →  ₹𝟏𝟎 𝐅𝐋𝐀𝐓"
    elif amount <= 2000:
        return "• ₹𝟏𝟎𝟎𝟏 𝐓𝐎 ₹𝟐𝟎𝟎𝟎       →  ₹𝟐𝟎 𝐅𝐋𝐀𝐓"
    elif amount <= 3000:
        return "• ₹𝟐𝟎𝟎𝟏 𝐓𝐎 ₹𝟑𝟎𝟎𝟎       →  𝟐.𝟓%"
    else:
        return "• 𝐔𝐏𝐏𝐄𝐑 𝐓𝐇𝐀𝐍 ₹𝟑𝟎𝟎𝟎     →  𝟐%"

def log_fee_calc(uid: int, amount: float, fee: float):
    """Log fee calculation to MongoDB"""
    fee_logs_col.insert_one({
        "user_id": uid,
        "amount": amount,
        "fee": fee,
        "date": datetime.now().isoformat()
    })

# ================= FORCE JOIN =================
async def is_joined_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    uid = update.effective_user.id
    channels = get_channels()
    if not channels:
        return False
    for _, link in channels:
        try:
            username = link.split("/")[-1].replace("@", "").strip()
            member = await context.bot.get_chat_member(f"@{username}", uid)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

async def force_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = get_channels()
    keyboard = build_channel_keyboard(channels, columns=2)
    keyboard.append([InlineKeyboardButton(
        "𝐂ʜᴇᴄᴋ 𝐉ᴏɪɴᴇᴅ ✅",
        callback_data="check"
    )])
    markup = InlineKeyboardMarkup(keyboard)
    msg_text = get_setting("force_msg", "⚠️ *Access Restricted!*\n\nPlease join all the channels below to use this bot.")
    image_url = get_setting("force_image", "")
    target = update.message or (update.callback_query.message if update.callback_query else None)
    if not target:
        return
    if image_url:
        await target.reply_photo(photo=image_url, caption=msg_text, reply_markup=markup, parse_mode="Markdown")
    else:
        await target.reply_text(msg_text, reply_markup=markup, parse_mode="Markdown")

async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    uid = update.effective_user.id
    if is_admin(uid):
        return True
    channels = get_channels()
    if not channels:
        return True
    if not await is_joined_all(update, context):
        await force_join(update, context)
        return False
    return True

# ================= /owner =================
async def owner_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if get_owner() is not None:
        if is_owner(uid):
            await update.message.reply_text("✅ You are already the OWNER!")
        else:
            await update.message.reply_text("⚠️ Owner is already set.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /owner <secret_password>")
        return
    secret = context.args[0].strip()
    if secret != OWNER_SECRET:
        await update.message.reply_text("❌ Wrong secret! Access denied.")
        return
    add_owner(uid)
    name = update.effective_user.first_name or "Owner"
    await update.message.reply_text(
        f"👑 Welcome, *{name}*!\n\nYou are now the *OWNER* of this bot.\nUse /start to see all commands.",
        parse_mode="Markdown"
    )

# ================= /start =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    save_user(uid)

    if get_owner() is None:
        await update.message.reply_text(
            "⚙️ Bot not configured yet.\n\nOwner must run: /owner <secret_password>"
        )
        return

    if not await guard(update, context):
        return

    if is_owner(uid):
        await update.message.reply_text(
            "👑 *Owner Panel*\n\n"
            "📋 *Channel Management*\n"
            "/add — Add channel\n"
            "/remove — Remove channel\n"
            "/update — Update channel link\n"
            "/list — List channels\n\n"
            "📢 *Broadcast*\n"
            "/broadcast — Broadcast to all users\n\n"
            "⚙️ *Settings*\n"
            "/setmsg — Set force join message\n"
            "/setimage — Set force join image\n\n"
            "👮 *Admin Management*\n"
            "/addadmin — Add admin\n"
            "/removeadmin — Remove admin\n"
            "/admins — List admins\n\n"
            "📊 *Stats & Tools*\n"
            "/stats — Bot statistics\n"
            "/p <amount> — Calculate total amount with fee\n"
            "/fees — View fee structure",
            parse_mode="Markdown"
        )
    elif is_admin(uid):
        await update.message.reply_text(
            "👮 *Admin Panel*\n\n"
            "/add — Add channel\n"
            "/remove — Remove channel\n"
            "/update — Update channel link\n"
            "/list — List channels\n"
            "/broadcast — Broadcast to all users\n"
            "/setmsg — Set force join message\n"
            "/setimage — Set force join image\n"
            "/stats — Bot statistics\n"
            "/p <amount> — Calculate total amount with fee\n"
            "/fees — View fee structure",
            parse_mode="Markdown"
        )
    else:
        name = update.effective_user.first_name or "User"
        await update.message.reply_text(
            f"✅ *Access Granted!* Welcome, {name}!\n\n"
            "Use /p <amount> to calculate your total amount with escrow fee.\n"
            "Use /fees to view the full fee structure.",
            parse_mode="Markdown"
        )

# ================= CALLBACK =================
async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if await is_joined_all(update, context):
        await q.edit_message_text("✅ Verified! Use /start to continue.")
    else:
        await q.answer("❌ Join all channels first!", show_alert=True)

# ================= /fees COMMAND =================
async def fees_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the full fee structure."""
    save_user(update.effective_user.id)
    if not await guard(update, context):
        return

    text = (
            "𝗖𝗛𝗔𝗥𝗚𝗘𝗦 𝗔𝗖𝗖𝗢𝗥𝗗𝗜𝗡𝗚 𝗧𝗢\n"
            "𝗗𝗘𝗔𝗟 𝗔𝗠𝗢𝗨𝗡𝗧 ‼️\n\n"
        
        "• 𝐔𝐍𝐃𝐄𝐑 ₹𝟓𝟎𝟎           →  ₹𝟓 𝐅𝐋𝐀𝐓\n"
        "• ₹𝟓𝟎𝟏 𝐓𝐎 ₹𝟏𝟎𝟎𝟎        →  ₹𝟏𝟎 𝐅𝐋𝐀𝐓\n"
        "• ₹𝟏𝟎𝟎𝟏 𝐓𝐎 ₹𝟐𝟎𝟎𝟎       →  ₹𝟐𝟎 𝐅𝐋𝐀𝐓\n"
        "• ₹𝟐𝟎𝟎𝟏 𝐓𝐎 ₹𝟑𝟎𝟎𝟎       →  𝟐.𝟓%\n"
        "• 𝐔𝐏𝐏𝐄𝐑 𝐓𝐇𝐀𝐍 ₹𝟑𝟎𝟎𝟎     →  𝟐%\n"
        "═══════════════════════════════\n"
        "💡 Use `/p <amount>` To Calculate\n"
        "   Total Amount With Fee\n\n"
        "🔐 Safe • Secure • Trusted\n"
        "RG ~ @PEACEESCROWSERVICE"
    )

    keyboard = [[InlineKeyboardButton("🧮 Calculate Now", switch_inline_query_current_chat="/p ")]]
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= /p COMMAND (formerly /fee) =================
async def calculate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Calculate total amount with fee for a given deal amount."""
    uid = update.effective_user.id
    save_user(uid)

    if not await guard(update, context):
        return

    # Parse amount from args
    raw = " ".join(context.args).strip() if context.args else ""
    amount = None
    if raw:
        clean = raw.replace(",", "").replace("₹", "").replace("rs", "").replace("RS", "").strip()
        try:
            amount = float(clean)
        except ValueError:
            amount = None

    if amount is None or amount <= 0:
        
        return

    # Send typing/searching animation message
    thinking_msg = await update.message.reply_text("🔍 Calculating total amount, please wait...")

    fee = calculate_fee(amount)
    slab = get_fee_slab(amount)
    total = amount + fee
    log_fee_calc(uid, amount, fee)

    # Delete the typing message
    await thinking_msg.delete()

    result = (
        "╔══════════════════════════\n"
        "║    𝗙𝗘𝗘 𝗖𝗔𝗟𝗖𝗨𝗟𝗔𝗧𝗘 𝗥𝗘𝗦𝗨𝗟𝗧 !!\n"
        "╚══════════════════════════\n\n"
        f"💰 *Deal Amount*        :  `₹{amount:,.2f}`\n"
        f"📊 *Applied Slab*       :  `{slab}`\n"
        f"💸 *Escrow Fees*        :  `₹{fee:,.2f}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ *Total Payable*      :  `₹{total:,.2f}`\n\n"
        "🔐 Safe • Secure • Trusted\n"
        "RG ~ @PEACEESCROWSERVICE"
    )

    keyboard = [
        [InlineKeyboardButton("🔁 Calculate Again", switch_inline_query_current_chat="/p ")]
    ]

    await update.message.reply_text(
        result,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= FEE KEYWORD AUTO-REPLY =================
KEYWORDS = ["fee", "fees"]

async def fee_keyword_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-reply fee structure when keywords are detected in chat."""
    if not update.message or not update.message.text:
        return
    text = update.message.text.lower()

    # Check for amount-only messages like "300" or "1500 ka fee"
    amount_match = re.search(r'\b(\d+(?:[.,]\d+)?)\b', text)
    has_fee_keyword = any(word in text for word in KEYWORDS)

    # If message is just a plain number (in private chat only), calculate total
    if update.message.chat.type == "private" and amount_match and not update.message.text.startswith("/"):
        raw_amount = amount_match.group(1).replace(",", "")
        try:
            amount = float(raw_amount)
            if 1 <= amount <= 1_000_000:
                uid = update.effective_user.id
                save_user(uid)
                channels = get_channels()
                if channels and not is_admin(uid):
                    if not await is_joined_all(update, context):
                        await force_join(update, context)
                        return

                thinking_msg = await update.message.reply_text("🔍 Calculating total amount...")
                fee = calculate_fee(amount)
                slab = get_fee_slab(amount)
                total = amount + fee
                log_fee_calc(uid, amount, fee)
                await thinking_msg.delete()

                result = (
                    "╔═════════════════════════\n"
                    "║    𝗙𝗘𝗘 𝗖𝗔𝗟𝗖𝗨𝗟𝗔𝗧𝗘 𝗥𝗘𝗦𝗨𝗟𝗧 !!\n"
                    "╚═════════════════════════\n\n"
                    f"💰 *Deal Amount*        :  `₹{amount:,.2f}`\n"
                    f"📊 *Applied Slab*       :  `{slab}`\n"
                    f"💸 *Escrow Fees*        :  `₹{fee:,.2f}`\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ *Total Payable*      :  `₹{total:,.2f}`\n\n"
                    "🔐 Safe • Secure • Trusted\n"
                    "RG ~ @PEACEESCROWSERVICE"
                )
                keyboard = [
                    [InlineKeyboardButton("📊 View Fee Structure", callback_data="show_fees")],
                    [InlineKeyboardButton("🔁 Calculate Again", switch_inline_query_current_chat="/p ")]
                ]
                await update.message.reply_text(result, parse_mode="Markdown",
                                                reply_markup=InlineKeyboardMarkup(keyboard))
                return
        except ValueError:
            pass

    # Fee keyword detected anywhere - show fee structure
    if has_fee_keyword:
        uid = update.effective_user.id
        save_user(uid)
        text_reply = (
            "𝗖𝗛𝗔𝗥𝗚𝗘𝗦 𝗔𝗖𝗖𝗢𝗥𝗗𝗜𝗡𝗚 𝗧𝗢\n"
            "𝗗𝗘𝗔𝗟 𝗔𝗠𝗢𝗨𝗡𝗧 ‼️\n\n"
     "• 𝐔𝐍𝐃𝐄𝐑 ₹𝟓𝟎𝟎           →  ₹𝟓 𝐅𝐋𝐀𝐓\n"

"• ₹𝟓𝟎𝟏 𝐓𝐎 ₹𝟏𝟎𝟎𝟎        →  ₹𝟏𝟎 𝐅𝐋𝐀𝐓\n"

"• ₹𝟏𝟎𝟎𝟏 𝐓𝐎 ₹𝟐𝟎𝟎𝟎       →  ₹𝟐𝟎 𝐅𝐋𝐀𝐓\n"

"• ₹𝟐𝟎𝟎𝟏 𝐓𝐎 ₹𝟑𝟎𝟎𝟎       →  𝟐.𝟓%\n"

"• 𝐔𝐏𝐏𝐄𝐑 𝐓𝐇𝐀𝐍 ₹𝟑𝟎𝟎𝟎     →  𝟐%\n"

            "══════════════════════\n"
            "💡 Use `/p <amount>` To Calculate\n"
            "   Total Amount With Fee\n\n"
            "🔐 Safe • Secure • Trusted\n"
            "RG ~ @PEACEESCROWSERVICE"
        )
        keyboard = [[InlineKeyboardButton("🧮 Calculate Now", switch_inline_query_current_chat="/p ")]]
        await update.message.reply_text(text_reply, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(keyboard))

# ================= CALLBACK: show_fees =================
async def show_fees_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    text = (
        "CHARGES ACCORDING TO\n"
        "DEAL AMOUNT ‼️     \n\n"
        "• UNDER ₹500           →  ₹5 FLAT\n"
        "• ₹501 TO ₹1000        →  ₹10 FLAT\n"
        "• ₹1001 TO ₹2000       →  ₹20 FLAT\n"
        "• ₹2001 TO ₹3000       →  2.5%\n"
        "• UPPER THAN ₹3000     →  2%\n"
        "═══════════════════════════════\n"
        "💡 Use `/p <amount>` To Calculate\n"
        "   Total Amount With Fee\n\n"
        "🔐 Safe • Secure • Trusted\n"
        "RG ~ @PEACEESCROWSERVICE"
    )
    await q.message.reply_text(text, parse_mode="Markdown")

# ================= CHANNEL MANAGEMENT =================
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        n = int(context.args[0])
        l = context.args[1]
        channels_col.update_one(
            {"number": n},
            {"$set": {"number": n, "link": l, "active": 1}},
            upsert=True
        )
        await update.message.reply_text(f"✅ Channel {n} added!")
    except Exception as e:
        await update.message.reply_text(f"Usage: /add 1 https://t.me/yourchannel\nError: {str(e)}")

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        n = int(context.args[0])
        channels_col.update_one(
            {"number": n},
            {"$set": {"active": 0}}
        )
        await update.message.reply_text(f"✅ Channel {n} removed!")
    except Exception:
        await update.message.reply_text("Usage: /remove 1")

async def update_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        n = int(context.args[0])
        l = context.args[1]
        channels_col.update_one(
            {"number": n},
            {"$set": {"link": l, "active": 1}}
        )
        await update.message.reply_text(f"✅ Channel {n} updated!")
    except Exception:
        await update.message.reply_text("Usage: /update 1 https://t.me/newlink")

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update, context):
        return
    ch = get_channels()
    if not ch:
        await update.message.reply_text("No channels added yet.")
        return
    msg = "*Active Channels:*\n\n"
    for n, l in ch:
        msg += f"`{n}` — {l}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def channel_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update, context):
        return
    ch = get_channels()
    if not ch:
        await update.message.reply_text("No channels available.")
        return
    kb = build_channel_keyboard(ch, columns=2)
    await update.message.reply_text("📢 Join our channels:", reply_markup=InlineKeyboardMarkup(kb))

# ================= SETTINGS =================
async def set_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    msg = " ".join(context.args).strip()
    if not msg:
        await update.message.reply_text("Usage: /setmsg Your message here")
        return
    set_setting("force_msg", msg)
    await update.message.reply_text(f"✅ Force message updated!\n\n{msg}")

async def set_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    url = " ".join(context.args).strip()
    if not url:
        await update.message.reply_text("Usage: /setimage https://...")
        return
    set_setting("force_image", url)
    await update.message.reply_text("✅ Force image updated!")

# ================= BROADCAST =================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    msg = " ".join(context.args).strip()
    if not msg:
        await update.message.reply_text("Usage: /broadcast your message")
        return
    
    user_rows = users_col.find({}, {"user_id": 1})
    success, fail = 0, 0
    for user in user_rows:
        try:
            await context.bot.send_message(chat_id=user["user_id"], text=msg)
            success += 1
        except Exception:
            fail += 1
    
    broadcasts_col.insert_one({
        "message": msg,
        "date": datetime.now().isoformat()
    })
    await update.message.reply_text(f"📢 *Broadcast Done!*\n\n✅ Sent: {success}\n❌ Failed: {fail}", parse_mode="Markdown")

# ================= ADMIN MANAGEMENT =================
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    try:
        uid = int(context.args[0])
        admins_col.update_one(
            {"user_id": uid},
            {"$set": {"role": "admin"}},
            upsert=True
        )
        await update.message.reply_text(f"✅ Admin `{uid}` added!", parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("Usage: /addadmin <user_id>")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    try:
        uid = int(context.args[0])
        if is_owner(uid):
            await update.message.reply_text("❌ Cannot remove owner!")
            return
        admins_col.delete_one({"user_id": uid})
        await update.message.reply_text(f"✅ Admin `{uid}` removed!", parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("Usage: /removeadmin <user_id>")

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    rows = admins_col.find({})
    msg = "*👮 Admins:*\n\n"
    for admin in rows:
        emoji = "👑" if admin["role"] == "owner" else "🛡️"
        msg += f"{emoji} `{admin['user_id']}` — {admin['role'].upper()}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ================= STATS =================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    ch = channels_col.count_documents({"active": 1})
    ad = admins_col.count_documents({})
    br = broadcasts_col.count_documents({})
    us = users_col.count_documents({})
    fc = fee_logs_col.count_documents({})
    
    await update.message.reply_text(
        "📊 *Bot Statistics*\n\n"
        f"📢 Channels: `{ch}`\n"
        f"👮 Admins: `{ad}`\n"
        f"👥 Users: `{us}`\n"
        f"📣 Broadcasts: `{br}`\n"
        f"🧮 Fee Calculations: `{fc}`\n"
        f"🟢 Status: Online",
        parse_mode="Markdown"
    )

# ================= MAIN =================
def main():
    init_db()
    Thread(target=run_web_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    # Core commands
    app.add_handler(CommandHandler("owner", owner_cmd))
    app.add_handler(CommandHandler("start", start))

    # Fee commands (updated from /fee to /p)
    app.add_handler(CommandHandler("p", calculate_cmd))
    app.add_handler(CommandHandler("fee", calculate_cmd))  # Keep backward compatibility
    app.add_handler(CommandHandler("fees", fees_cmd))

    # Channel management
    app.add_handler(CommandHandler("add", add_channel))
    app.add_handler(CommandHandler("remove", remove_channel))
    app.add_handler(CommandHandler("update", update_channel))
    app.add_handler(CommandHandler("list", list_channels))
    app.add_handler(CommandHandler("channels", channel_buttons))

    # Broadcast
    app.add_handler(CommandHandler("broadcast", broadcast))

    # Admin management
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("admins", list_admins))

    # Stats & Settings
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("setmsg", set_message))
    app.add_handler(CommandHandler("setimage", set_image))

    # Callbacks
    app.add_handler(CallbackQueryHandler(check_join, pattern="^check$"))
    app.add_handler(CallbackQueryHandler(show_fees_callback, pattern="^show_fees$"))

    # Auto keyword handler (groups + private)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        fee_keyword_handler
    ))

    logger.warning("🚀 PEACE Escrow Bot started with MongoDB!")
    app.run_polling()

if __name__ == "__main__":
    main()
