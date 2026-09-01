import asyncio
import random
from pathlib import Path

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================
# НАСТРОЙКИ
# =========================

BOT_TOKEN = "8660296617:AAGFfqM8_6OzEvQCWOjzzT5o1fOnWFifIH0"

DB_NAME = Path("casino.db")

START_BALANCE = 1000
BONUS_AMOUNT = 100

# Шанс победы: 45%
WIN_CHANCE = 0.45


# =========================
# БАЗА ДАННЫХ
# =========================

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 1000
            )
        """)
        await db.commit()


async def create_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO users (user_id, balance)
            VALUES (?, ?)
            """,
            (user_id, START_BALANCE),
        )
        await db.commit()


async def get_balance(user_id: int) -> int:
    await create_user(user_id)

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT balance FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0]


async def change_balance(user_id: int, amount: int) -> int:
    await create_user(user_id)

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
            """,
            (amount, user_id),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT balance FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0]


# =========================
# КЛАВИАТУРА
# =========================

def main_keyboard():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🎰 Играть",
        callback_data="play",
    )

    builder.button(
        text="💰 Баланс",
        callback_data="balance",
    )

    builder.button(
        text="🎁 Получить бонус",
        callback_data="bonus",
    )

    builder.adjust(2, 1)

    return builder.as_markup()


def back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔙 Главное меню",
        callback_data="menu",
    )
    return builder.as_markup()


# =========================
# /START
# =========================

async def start_handler(message: Message):
    user_id = message.from_user.id
    balance = await get_balance(user_id)

    await message.answer(
        "🎰 <b>Добро пожаловать в казино!</b>\n\n"
        f"💰 Баланс: <b>{balance}</b> виртуальных монет\n\n"
        "Выбери действие:",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


# =========================
# /ID
# =========================

async def id_handler(message: Message):
    await message.answer(
        f"🆔 Твой Telegram ID:\n\n"
        f"<code>{message.from_user.id}</code>",
        parse_mode="HTML",
    )


# =========================
# БАЛАНС
# =========================

async def balance_handler(callback: CallbackQuery):
    balance = await get_balance(callback.from_user.id)

    await callback.message.edit_text(
        "💰 <b>Твой баланс</b>\n\n"
        f"<b>{balance}</b> виртуальных монет",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )

    await callback.answer()


# =========================
# ИГРА
# =========================

async def play_handler(callback: CallbackQuery):
    balance = await get_balance(callback.from_user.id)

    if balance <= 0:
        await callback.message.edit_text(
            "💸 <b>Монеты закончились.</b>\n\n"
            "Попробуй получить бонус.",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "🎰 <b>Сделай ставку</b>\n\n"
        f"💰 Баланс: <b>{balance}</b>\n"
        f"🎯 Шанс победы: <b>{WIN_CHANCE * 100:.0f}%</b>\n\n"
        "Отправь в чат целое число.\n"
        "Например: <code>100</code>",
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )

    await callback.answer()


# =========================
# СТАВКА
# =========================

async def bet_handler(message: Message):
    text = (message.text or "").strip()

    if not text.isdigit():
        return

    bet = int(text)

    if bet <= 0:
        await message.answer("❌ Ставка должна быть больше 0.")
        return

    # Защита от слишком больших чисел.
    if bet > 10**9:
        await message.answer("❌ Слишком большая ставка.")
        return

    user_id = message.from_user.id
    balance = await get_balance(user_id)

    if bet > balance:
        await message.answer(
            "❌ <b>Недостаточно монет.</b>\n\n"
            f"💰 Баланс: <b>{balance}</b>\n"
            f"🎲 Ставка: <b>{bet}</b>",
            parse_mode="HTML",
        )
        return

    # Сначала списываем ставку.
    await change_balance(user_id, -bet)

    # Затем определяем результат.
    if random.random() < WIN_CHANCE:
        # Победа: возвращаем ставку + выигрыш такого же размера.
        new_balance = await change_balance(user_id, bet * 2)

        await message.answer(
            "🎉 <b>ТЫ ВЫИГРАЛ!</b>\n\n"
            f"🎲 Ставка: <b>{bet}</b>\n"
            f"💰 Выигрыш: <b>+{bet}</b>\n\n"
            f"💵 Новый баланс: <b>{new_balance}</b>",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
    else:
        new_balance = await get_balance(user_id)

        await message.answer(
            "😔 <b>ТЫ ПРОИГРАЛ</b>\n\n"
            f"🎲 Ставка: <b>{bet}</b>\n"
            f"💸 Потеря: <b>-{bet}</b>\n\n"
            f"💵 Новый баланс: <b>{new_balance}</b>",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )


# =========================
# БОНУС
# =========================

async def bonus_handler(callback: CallbackQuery):
    new_balance = await change_balance(
        callback.from_user.id,
        BONUS_AMOUNT,
    )

    await callback.message.edit_text(
        "🎁 <b>Бонус получен!</b>\n\n"
        f"Начислено: <b>+{BONUS_AMOUNT}</b> монет\n\n"
        f"💰 Новый баланс: <b>{new_balance}</b>",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )

    await callback.answer(
        f"🎁 +{BONUS_AMOUNT} монет!"
    )


# =========================
# ГЛАВНОЕ МЕНЮ
# =========================

async def menu_handler(callback: CallbackQuery):
    balance = await get_balance(callback.from_user.id)

    await callback.message.edit_text(
        "🎰 <b>Главное меню</b>\n\n"
        f"💰 Баланс: <b>{balance}</b> виртуальных монет",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )

    await callback.answer()


# =========================
# ЗАПУСК
# =========================

async def main():
    if BOT_TOKEN == "ВСТАВЬ_СЮДА_ТОКЕН_БОТА":
        raise RuntimeError(
            "Вставь токен Telegram-бота в переменную BOT_TOKEN."
        )

    await init_db()

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    # Команды
    dp.message.register(
        start_handler,
        CommandStart(),
    )

    dp.message.register(
        id_handler,
        Command("id"),
    )

    # Кнопки
    dp.callback_query.register(
        play_handler,
        F.data == "play",
    )

    dp.callback_query.register(
        balance_handler,
        F.data == "balance",
    )

    dp.callback_query.register(
        bonus_handler,
        F.data == "bonus",
    )

    dp.callback_query.register(
        menu_handler,
        F.data == "menu",
    )

    # Ставки — только целые числа.
    dp.message.register(
        bet_handler,
        F.text,
        lambda message: (message.text or "").strip().isdigit(),
    )

    print("🎰 Казино-бот запущен!")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
