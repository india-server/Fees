import os
import re
import time
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("PeaceEscrowBot")

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable missing.")

PORT = int(os.environ.get("PORT", 10000))

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# =========================================================
# MESSAGE
# =========================================================

FEE_MESSAGE = """
╔══════════════════════════════╗
║   💰 PEACE ESCROW SERVICE   ║
║      FEES STRUCTURE 📊      ║
╚══════════════════════════════╝

📐 DEAL AMOUNT ──▶ CHARGES

💵 Under RS 500         ▶ RS 5
💵 RS 501 – RS 1000    ▶ 1%
💵 RS 1001 – RS 2000   ▶ 2%
💵 RS 2001 – RS 3000   ▶ 2.5%
💵 Above RS 3000       ▶ 3%

🔐 Safe • Secure • Trusted

RG ~ @PEACEEscrowService
"""

# =========================================================
# HEALTH CHECK SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Peace Escrow Bot Running")

    def log_message(self, format, *args):
        return


def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)

    logger.info(f"🌐 Health server running on port {PORT}")

    server.serve_forever()

# =========================================================
# KEYWORD CHECK
# =========================================================

def contains_fee_keyword(text: str) -> bool:
    if not text:
        return False

    pattern = r"\b(fee|fees|charge|charges|pricing|rate|rates)\b"

    return bool(re.search(pattern, text, re.IGNORECASE))

# =========================================================
# TELEGRAM API
# =========================================================

def get_updates(offset=None):

    url = f"{BASE_URL}/getUpdates"

    params = {
        "timeout": 30,
        "allowed_updates": ["message"]
    }

    if offset:
        params["offset"] = offset

    try:

        response = requests.get(
            url,
            params=params,
            timeout=35
        )

        data = response.json()

        if not data.get("ok"):
            logger.error(f"Telegram API Error: {data}")

        return data

    except Exception as e:
        logger.error(f"getUpdates Exception: {e}")
        return None


def send_message(chat_id, text, reply_to_message_id=None):

    url = f"{BASE_URL}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=15
        )

        data = response.json()

        if not data.get("ok"):
            logger.error(f"sendMessage Error: {data}")

        return data

    except Exception as e:
        logger.error(f"sendMessage Exception: {e}")
        return None

# =========================================================
# PROCESS UPDATES
# =========================================================

def process_update(update):

    message = update.get("message")

    if not message:
        return

    text = message.get("text", "")

    chat = message.get("chat", {})

    chat_type = chat.get("type")
    chat_id = chat.get("id")

    message_id = message.get("message_id")

    # Only groups/supergroups/private
    if chat_type not in ("group", "supergroup", "private"):
        return

    if contains_fee_keyword(text):

        logger.info(
            f"💰 Fee keyword detected | Chat: {chat_id}"
        )

        send_message(
            chat_id=chat_id,
            text=FEE_MESSAGE,
            reply_to_message_id=message_id
        )

# =========================================================
# MAIN
# =========================================================

def main():

    # Start health server
    threading.Thread(
        target=run_health_server,
        daemon=True
    ).start()

    logger.info("🚀 Peace Escrow Bot polling started...")

    offset = None

    while True:

        try:

            updates_data = get_updates(offset)

            if not updates_data:

                logger.warning(
                    "No response from Telegram API."
                )

                time.sleep(5)
                continue

            if not updates_data.get("ok"):

                logger.warning(
                    "Telegram returned non-ok response."
                )

                time.sleep(5)
                continue

            updates = updates_data.get("result", [])

            for update in updates:

                offset = update["update_id"] + 1

                process_update(update)

        except KeyboardInterrupt:

            logger.info("Bot stopped manually.")
            break

        except Exception as e:

            logger.exception(
                f"Unexpected Main Loop Error: {e}"
            )

            time.sleep(5)

# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
