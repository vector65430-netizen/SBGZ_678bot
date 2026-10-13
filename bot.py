import os
import io
import ast
import math
import random
import string
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import qrcode
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN is missing. Add it in Railway variables.")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("SBGZ_678bot")

# ---------- Simple in-memory rate limiter ----------
USER_LAST_CMD = {}
COOLDOWN_SECONDS = 1.5


def rate_limited(user_id: int) -> bool:
    now = datetime.utcnow().timestamp()
    last = USER_LAST_CMD.get(user_id, 0)
    if now - last < COOLDOWN_SECONDS:
        return True
    USER_LAST_CMD[user_id] = now
    return False


# ---------- Command: /start ----------
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "friend"
    keyboard = [
        [InlineKeyboardButton("📖 Help", callback_data="help"),
         InlineKeyboardButton("🆔 My ID", callback_data="myid")],
        [InlineKeyboardButton("🎲 Dice", callback_data="dice"),
         InlineKeyboardButton("🪙 Flip", callback_data="flip")],
    ]
    await update.message.reply_text(
        f"👋 Hello <b>{name}</b>!\n\n"
        "I'm <b>SBGZ_678bot</b> — your multi-purpose assistant.\n\n"
        "Use /help to see everything I can do.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------- Command: /help ----------
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>🤖 SBGZ_678bot — Commands</b>\n\n"
        "<b>Utility</b>\n"
        "/id – Show your Telegram ID\n"
        "/qr &lt;text&gt; – Generate a QR code\n"
        "/password [length] – Strong password\n"
        "/shorten &lt;url&gt; – Shorten a URL\n\n"
        "<b>Info</b>\n"
        "/crypto &lt;symbol&gt; – Crypto price (e.g. btc)\n"
        "/weather &lt;city&gt; – Current weather\n"
        "/wiki &lt;topic&gt; – Wikipedia summary\n"
        "/time &lt;zone&gt; – Time in a timezone\n\n"
        "<b>Tools</b>\n"
        "/convert &lt;amt&gt; &lt;from&gt; &lt;to&gt; – Currency\n"
        "/calc &lt;expr&gt; – Calculator\n\n"
        "<b>Fun</b>\n"
        "/dice [sides] – Roll a dice\n"
        "/flip – Flip a coin\n"
        "/poll &lt;question&gt; – Yes/No poll\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ---------- Command: /id ----------
async def id_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await update.message.reply_text(
        f"🆔 <b>Your Info</b>\n"
        f"User ID: <code>{u.id}</code>\n"
        f"Username: @{u.username if u.username else 'N/A'}\n"
        f"Chat ID: <code>{update.effective_chat.id}</code>",
        parse_mode=ParseMode.HTML,
    )


# ---------- Command: /qr ----------
async def qr_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("Usage: /qr <text or url>")
    data = " ".join(ctx.args)[:1000]
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    await update.message.reply_photo(buf, caption="✅ QR code generated.")


# ---------- Command: /password ----------
async def password_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    length = 16
    if ctx.args:
        try:
            length = max(8, min(64, int(ctx.args[0])))
        except ValueError:
            return await update.message.reply_text("Usage: /password [8-64]")
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    pwd = "".join(random.SystemRandom().choice(alphabet) for _ in range(length))
    await update.message.reply_text(
        f"🔐 <b>Your password</b> ({length} chars):\n<code>{pwd}</code>\n\n"
        "<i>Do not share this message.</i>",
        parse_mode=ParseMode.HTML,
    )


# ---------- Command: /shorten ----------
async def shorten_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("Usage: /shorten https://example.com")
    url = ctx.args[0]
    if not url.startswith(("http://", "https://")):
        return await update.message.reply_text("❌ URL must start with http:// or https://")
    try:
        r = requests.get(
            "https://tinyurl.com/api-create.php",
            params={"url": url},
            timeout=10,
        )
        if r.status_code == 200 and r.text.startswith("http"):
            await update.message.reply_text(f"🔗 Short URL:\n{r.text}")
        else:
            await update.message.reply_text("❌ Could not shorten that URL.")
    except Exception as e:
        logger.warning("shorten error: %s", e)
        await update.message.reply_text("⚠️ Service unavailable. Try later.")


# ---------- Command: /crypto ----------
async def crypto_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("Usage: /crypto btc")
    symbol = ctx.args[0].lower()
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": symbol, "vs_currencies": "usd,eur"},
            timeout=10,
        )
        data = r.json()
        if symbol not in data:
            return await update.message.reply_text(
                f"❌ Unknown coin '<b>{symbol}</b>'. Try: btc, eth, doge, sol, xrp.",
                parse_mode=ParseMode.HTML,
            )
        usd = data[symbol].get("usd")
        eur = data[symbol].get("eur")
        await update.message.reply_text(
            f"💰 <b>{symbol.upper()}</b>\n"
            f"USD: <code>${usd:,}</code>\n"
            f"EUR: <code>€{eur:,}</code>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning("crypto error: %s", e)
        await update.message.reply_text("⚠️ Could not fetch price right now.")


# ---------- Command: /weather ----------
async def weather_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("Usage: /weather <city>")
    city = " ".join(ctx.args)
    try:
        # Open-Meteo (free, no API key)
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
            timeout=10,
        ).json()
        if not geo.get("results"):
            return await update.message.reply_text("❌ City not found.")
        loc = geo["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        name = f"{loc['name']}, {loc.get('country', '')}".strip(", ")

        w = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,wind_speed_10m,relative_humidity_2m,weather_code",
            },
            timeout=10,
        ).json().get("current", {})

        code = w.get("weather_code", 0)
        desc = weather_code_desc(code)

        await update.message.reply_text(
            f"🌍 <b>{name}</b>\n"
            f"🌡 Temp: <code>{w.get('temperature_2m')}°C</code>\n"
            f"💧 Humidity: <code>{w.get('relative_humidity_2m')}%</code>\n"
            f"💨 Wind: <code>{w.get('wind_speed_10m')} km/h</code>\n"
            f"☁️ {desc}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning("weather error: %s", e)
        await update.message.reply_text("⚠️ Weather service unavailable.")


def weather_code_desc(code: int) -> str:
    mapping = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Rain showers", 81: "Rain showers", 82: "Violent showers",
        95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Thunderstorm w/ heavy hail",
    }
    return mapping.get(code, "Unknown")


# ---------- Command: /wiki ----------
async def wiki_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("Usage: /wiki <topic>")
    topic = " ".join(ctx.args)
    try:
        r = requests.get(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + topic.replace(" ", "_"),
            headers={"User-Agent": "SBGZ_678bot/1.0"},
            timeout=10,
        )
        if r.status_code != 200:
            return await update.message.reply_text("❌ No article found.")
        data = r.json()
        extract = data.get("extract", "No summary.")
        url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
        await update.message.reply_text(
            f"📚 <b>{data.get('title')}</b>\n\n{extract[:900]}\n\n🔗 {url}",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
        )
    except Exception as e:
        logger.warning("wiki error: %s", e)
        await update.message.reply_text("⚠️ Wikipedia unavailable.")


# ---------- Command: /time ----------
async def time_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("Usage: /time Asia/Tokyo")
    tz_name = ctx.args[0]
    try:
        now = datetime.now(ZoneInfo(tz_name))
        await update.message.reply_text(
            f"🕐 <b>{tz_name}</b>\n<code>{now.strftime('%Y-%m-%d %H:%M:%S')}</code>",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await update.message.reply_text("❌ Invalid timezone. Example: Asia/Tokyo, Europe/Paris")


# ---------- Command: /convert ----------
async def convert_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) != 3:
        return await update.message.reply_text("Usage: /convert 100 USD EUR")
    try:
        amount = float(ctx.args[0])
        frm = ctx.args[1].upper()
        to = ctx.args[2].upper()
    except ValueError:
        return await update.message.reply_text("❌ Invalid amount.")
    try:
        r = requests.get(
            "https://api.frankfurter.app/latest",
            params={"amount": amount, "from": frm, "to": to},
            timeout=10,
        ).json()
        if "rates" not in r or to not in r["rates"]:
            return await update.message.reply_text("❌ Unsupported currency pair.")
        result = r["rates"][to]
        await update.message.reply_text(
            f"💱 <b>{amount} {frm}</b> = <b>{result:.2f} {to}</b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning("convert error: %s", e)
        await update.message.reply_text("⚠️ Currency service unavailable.")


# ---------- Command: /calc ----------
ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod,
    ast.USub, ast.UAdd, ast.FloorDiv,
)


def safe_eval(expr: str):
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError("Unsafe expression")
    return eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, {})


async def calc_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("Usage: /calc 2+2*5")
    expr = " ".join(ctx.args)
    try:
        result = safe_eval(expr)
        await update.message.reply_text(
            f"🧮 <code>{expr}</code> = <b>{result}</b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await update.message.reply_text("❌ Invalid expression.")


# ---------- Command: /dice ----------
async def dice_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sides = 6
    if ctx.args:
        try:
            sides = max(2, min(1000, int(ctx.args[0])))
        except ValueError:
            pass
    roll = random.randint(1, sides)
    await update.message.reply_text(f"🎲 You rolled a <b>{roll}</b> (1–{sides})", parse_mode=ParseMode.HTML)


# ---------- Command: /flip ----------
async def flip_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    result = random.choice(["Heads 🪙", "Tails 🪙"])
    await update.message.reply_text(f"Result: <b>{result}</b>", parse_mode=ParseMode.HTML)


# ---------- Command: /poll ----------
async def poll_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("Usage: /poll Is Python the best language?")
    question = " ".join(ctx.args)[:290]
    await update.message.reply_poll(
        question=question,
        options=["Yes ✅", "No ❌"],
        is_anonymous=False,
    )


# ---------- Inline button callbacks ----------
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "help":
        await query.message.reply_text("Use /help to see all commands.")
    elif data == "myid":
        await query.message.reply_text(f"Your ID: <code>{query.from_user.id}</code>", parse_mode=ParseMode.HTML)
    elif data == "dice":
        await query.message.reply_text(f"🎲 You rolled a <b>{random.randint(1,6)}</b>", parse_mode=ParseMode.HTML)
    elif data == "flip":
        await query.message.reply_text(f"🪙 {random.choice(['Heads','Tails'])}")


# ---------- Fallback ----------
async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤔 Unknown command. Type /help.")


async def text_fallback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! I only respond to commands. Type /help to see what I can do."
    )


# ---------- Error handler ----------
async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling update:", exc_info=ctx.error)


# ---------- Main ----------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("qr", qr_cmd))
    app.add_handler(CommandHandler("password", password_cmd))
    app.add_handler(CommandHandler("shorten", shorten_cmd))
    app.add_handler(CommandHandler("crypto", crypto_cmd))
    app.add_handler(CommandHandler("weather", weather_cmd))
    app.add_handler(CommandHandler("wiki", wiki_cmd))
    app.add_handler(CommandHandler("time", time_cmd))
    app.add_handler(CommandHandler("convert", convert_cmd))
    app.add_handler(CommandHandler("calc", calc_cmd))
    app.add_handler(CommandHandler("dice", dice_cmd))
    app.add_handler(CommandHandler("flip", flip_cmd))
    app.add_handler(CommandHandler("poll", poll_cmd))

    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_fallback))

    app.add_error_handler(on_error)

    logger.info("🤖 SBGZ_678bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
