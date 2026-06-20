"""
Echo bot — рекомендуемый пример использования Telemelya.

Один и тот же код работает во всех режимах — переключение через переменные окружения:

Тестовый режим (mock-сервер Telemelya, webhook):
    TELEMELYA_URL=http://localhost:8080 python bot.py

Продакшн (реальный Telegram API, polling):
    BOT_TOKEN=<real_token> python bot.py

Продакшн через прокси:
    BOT_TOKEN=<real_token> PROXY_URL=http://127.0.0.1:12334 python bot.py

Продакшн (webhook):
    BOT_TOKEN=<real_token> WEBHOOK_URL=https://example.com python bot.py

Помимо эха, бот демонстрирует интерактивные сценарии (issue #3):
inline-клавиатуры с правкой «на месте», callback-алерты, inline-режим и
обработку фото с реальными байтами.
"""

import logging

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart

from telemelya.aiogram import TemelyaRunner

logging.basicConfig(level=logging.INFO)

dp = Dispatcher()

SHARE_QUERY = "моя консультация"


@dp.message(CommandStart())
async def handle_start(message: types.Message):
    await message.answer("Добро пожаловать!")


@dp.message(Command("menu"))
async def handle_menu(message: types.Message):
    """Сообщение с inline-кнопкой — для проверки edit-in-place + callback-алерта."""
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Поделиться", callback_data="share")]
        ]
    )
    await message.answer("Меню", reply_markup=kb)


@dp.callback_query(F.data == "share")
async def handle_share_callback(callback: types.CallbackQuery):
    """Правит клавиатуру того же сообщения и показывает алерт."""
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Готово ✓", callback_data="noop")]
        ]
    )
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer("Сохранено", show_alert=True)


@dp.message(Command("share"))
async def handle_share(message: types.Message):
    """Сообщение с кнопкой switch_inline_query — старт inline-шаринга «via @bot»."""
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(
                text="Поделиться через бота", switch_inline_query=SHARE_QUERY
            )]
        ]
    )
    await message.answer("Поделиться консультацией:", reply_markup=kb)


@dp.inline_query()
async def handle_inline_query(query: types.InlineQuery):
    """Отвечает на inline-запрос статьёй с готовым текстом сообщения."""
    article = types.InlineQueryResultArticle(
        id="consult-1",
        title="Отправить консультацию",
        input_message_content=types.InputTextMessageContent(
            message_text=f"Консультация по запросу «{query.query}» 🌱"
        ),
    )
    await query.answer(results=[article], cache_time=1, is_personal=True)


@dp.message(F.photo)
async def handle_photo(message: types.Message, bot: Bot):
    """Скачивает реальные байты фото и подтверждает их размер (vision-пайплайн)."""
    file = await bot.get_file(message.photo[-1].file_id)
    buffer = await bot.download_file(file.file_path)
    data = buffer.read() if hasattr(buffer, "read") else buffer
    await message.answer(f"Фото получено: {len(data)} байт")


@dp.message()
async def handle_echo(message: types.Message):
    await message.answer(message.text or "")


if __name__ == "__main__":
    runner = TemelyaRunner(dp)
    runner.run()
