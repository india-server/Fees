import os
import re
import logging
import time
import requests

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

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

def contains_fee_keyword(text):
    if not text:
        return False
    pattern = r'\b(fee|fees)\b'
    return bool(re.search(pattern, text, re.IGNORECASE))

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

    # Only respond in groups and supergroups
    if chat_type not in ["group", "supergroup"]:
        return

    if contains_fee_keyword(text):
        logger.info(f"Fee keyword detected in chat {chat_id}, message: {text[:50]}")
        send_message(chat_id, FEE_MESSAGE, reply_to_message_id=message_id)

def main():
    logger.info("🚀 Peace Escrow Bot started (Polling mode)...")
    offset = None

    while True:
        try:
            updates_data = get_updates(offset)

            if not updates_data or not updates_data.get("ok"):
                logger.warning("Failed to get updates, retrying in 5 seconds...")
                time.sleep(5)
                continue

            updates = updates_data.get("result", [])

            for update in updates:
                update_id = update.get("update_id")
                process_update(update)
                offset = update_id + 1

        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
