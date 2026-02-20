import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

from db import get_connection, init_db

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Бот лабы 5\n"
        "/add <текст> — добавить запись\n"
        "/list — показать записи"
    )


@dp.message(Command("add"))
async def add_note(message: types.Message):
    text = message.text.replace("/add", "").strip()
    if not text:
        await message.answer("Использование: /add текст")
        return

    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO notes (text) VALUES (%s);",
                (text,)
            )
    conn.close()

    await message.answer("Запись добавлена")


@dp.message(Command("list"))
async def list_notes(message: types.Message):
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, text FROM notes ORDER BY id;")
            rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.answer("Записей нет")
        return

    result = "\n".join(f"{r[0]}. {r[1]}" for r in rows)
    await message.answer(result)


async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
