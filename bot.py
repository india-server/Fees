import os
import re
import logging
import time
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
PORT = int(os.environ.get("PORT", 10000))

FEE_MESSAGE = """
╔══════════════════════════════╗
║   💰 𝗣𝗘𝗔𝗖𝗘 𝗘𝗦𝗖𝗥𝗢𝗪 𝗦𝗘𝗥𝗩𝗜𝗖𝗘   ║
║      𝗙𝗘𝗘𝗦 𝗦𝗧𝗥𝗨𝗖𝗧𝗨𝗥𝗘 📊      ║
╚══════════════════════════════╝

📐 𝗗𝗘𝗔𝗟 𝗔𝗠𝗢𝗨𝗡𝗧 ──▶ 𝗖𝗛𝗔𝗥𝗚𝗘𝗦

┌─────────────────────────────┐
│ 💵 𝗨𝗻𝗱𝗲𝗿 𝗥𝗦 𝟱𝟬𝟬         ▶  𝗥𝗦 𝟱 │
├─────────────────────────────┤
│ 💵 𝗥𝗦 𝟱𝟬𝟭 – 𝗥𝗦 𝟭𝟬𝟬𝟬    ▶  𝟭%   │
├─────────────────────────────┤
│ 💵 𝗥𝗦 𝟭𝟬𝟬𝟭 – 𝗥𝗦 𝟮𝟬𝟬𝟬   ▶  𝟮%   │
├─────────────────────────────┤
│ 💵 𝗥𝗦 𝟮𝟬𝟬𝟭 – 𝗥𝗦 𝟯𝟬𝟬𝟬   ▶  𝟮.𝟱% │
├─────────────────────────────┤
│ 💵 𝗔𝗯𝗼𝘃𝗲 𝗥𝗦 𝟯𝟬𝟬𝟬       ▶  𝟯%   │
└─────────────────────────────┘

🔐 𝗦𝗮𝗳𝗲 • 𝗦𝗲𝗰𝘂𝗿𝗲 • 𝗧𝗿𝘂𝘀𝘁𝗲𝗱

𝗥𝗚 ~ @𝗣𝗘𝗔𝗖𝗘𝗘𝗦𝗖𝗥𝗢𝗪𝗦𝗘𝗥𝗩𝗜𝗖𝗘 🫶❤️‍🩹
"""

# ── Dummy HTTP server so Render sees an open port ──────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Peace Escrow Bot is running!")

    def log_message(self, format, *args):
        pass  # Suppress noisy access logs

def run_http_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"🌐 Health-check server listening on port {PORT}")
    server.serve_forever()

# ── Telegram helpers ────────────────────────────────────────────────────────
def contains_fee_keyword(text):
    if not text:
        return False
    return bool(re.search(r'\b(fee|fees)\b', text, re.IGNORECASE))

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 30, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    try:
        response = requests.get(url, params=params, timeout=35)
        return response.json()
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return None

def send_message(chat_id, text, reply_to_message_id=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return None

def process_update(update):
    message = update.get("message")
    if not message:
        return

    text = message.get("text", "")
    chat = message.get("chat", {})
    chat_type = chat.get("type", "")
    chat_id = chat.get("id")
    message_id = message.get("message_id")

    # Works in groups, supergroups AND private chats
    if chat_type not in ["group", "supergroup", "private"]:
        return

    if contains_fee_keyword(text):
        logger.info(f"Fee keyword detected in {chat_type} {chat_id}")
        send_message(chat_id, FEE_MESSAGE, reply_to_message_id=message_id)

# ── Main ────────────────────────────────────────────────────────────────────
def main():
    # Start HTTP server in background thread
    t = threading.Thread(target=run_http_server, daemon=True)
    t.start()

    logger.info("🚀 Peace Escrow Bot polling started...")
    offset = None

    while True:
        try:
            updates_data = get_updates(offset)

            if not updates_data or not updates_data.get("ok"):
                logger.warning("Failed to get updates, retrying in 5s...")
                time.sleep(5)
                continue

            for update in updates_data.get("result", []):
                process_update(update)
                offset = update["update_id"] + 1

        except KeyboardInterrupt:
            logger.info("Bot stopped.")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
