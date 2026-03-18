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
"""

import logging

from aiogram import Dispatcher, types
from aiogram.filters import CommandStart

from telemelya.aiogram import TemelyaRunner

logging.basicConfig(level=logging.INFO)

dp = Dispatcher()


@dp.message(CommandStart())
async def handle_start(message: types.Message):
    await message.answer("Добро пожаловать!")


@dp.message(lambda message: message.photo)
async def handle_photo(message: types.Message):
    await message.answer_photo(
        photo=message.photo[-1].file_id,
        caption="Фото получено",
    )


@dp.message()
async def handle_echo(message: types.Message):
    await message.answer(message.text or "")


if __name__ == "__main__":
    runner = TemelyaRunner(dp)
    runner.run()
