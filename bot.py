import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable missing.")

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
# KEYWORD CHECK
# =========================================================

KEYWORDS = [
    "fee",
    "fees",
    "charge",
    "charges",
    "pricing",
    "rate",
    "rates"
]

# =========================================================
# MESSAGE HANDLER
# =========================================================

async def fee_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = (update.message.text or "").lower()

    if any(word in text for word in KEYWORDS):

        logger.info(
            f"Fee keyword detected | Chat: {update.effective_chat.id}"
        )

        await update.message.reply_text(
            FEE_MESSAGE
        )

# =========================================================
# MAIN
# =========================================================

def main():

    logger.info("🚀 Bot Started...")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            fee_handler
        )
    )

    app.run_polling()

# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
