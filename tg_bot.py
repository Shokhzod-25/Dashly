import base64
import asyncio
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram import F
from aiogram import types
import io
import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)


router = Router()


@router.message(Command("start"))
async def handler_start(msg: types.Message):
    await msg.answer(
        "📊 Привет! Отправь мне CSV-файл с продажами, чтобы я сделал анализ."
    )



@router.message(F.content_type == "document")
async def handle_document(msg: types.Message):
    document = msg.document

    if not document.file_name or not document.file_name.lower().endswith(".csv"):
        await msg.answer("⚠️ Пожалуйста, загрузите CSV-файл с данными о продажах.")
        return

    await msg.answer("📊 Анализирую данные... пожалуйста, подожди ⏳")

    try:
        # Скачивание файла
        file_bytes_io = io.BytesIO()
        await msg.bot.download(document, destination=file_bytes_io)
        file_bytes_io.seek(0)

        # Подготовка FormData для aiohttp
        form_data = aiohttp.FormData()
        form_data.add_field('file', 
                          file_bytes_io.getvalue(), 
                          filename=document.file_name,
                          content_type='text/csv')
        form_data.add_field('period', 'week')

        # Асинхронный запрос
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:8000/analyze",
                data=form_data,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    await msg.answer(f"⚠️ Ошибка анализа: {error_text}")
                    return

                report = await response.json()

        # Остальная логика отправки отчета...
        image_bytes = base64.b64decode(report["chart_png_base64"])
        image_file = types.BufferedInputFile(image_bytes, filename="chart.png")

        caption = report.get("text_report", "📊 Отчет по продажам")
        if len(caption) > 1024:
            caption = caption[:1021] + "..."

        await msg.answer_photo(
            photo=image_file,
            caption=caption,
            parse_mode="Markdown",
        )

    except asyncio.TimeoutError:
        await msg.answer("⏰ Время обработки истекло. Попробуйте еще раз.")
    
    except aiohttp.ClientError as e:
        await msg.answer(f"🌐 Ошибка соединения: {e}")
    
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {str(e)}")
async def main():
    bot = Bot(token="8022350360:AAF2zifWihlUoYz0q_GQ1xPCHKJ0vA-hvVQ")
    dp = Dispatcher()
    dp.include_router(router)

    print("🤖 DashlyBot запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
