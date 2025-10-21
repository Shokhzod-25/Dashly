import base64
import asyncio
import requests
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command

router = Router()


@router.message(Command("start"))
async def handler_start(msg: types.Message):
    """Обработчик /start — отправляет демо-отчёт"""

    await msg.answer("📊 Анализирую данные... пожалуйста, подожди ⏳")

    try:
        with open("demo_sales.csv", "rb") as f:
            files = {"file": f}
            data = {"period": "week"}
            response = requests.post(
                "http://localhost:8000/analyze", files=files, data=data, timeout=30
            )

        if response.status_code != 200:
            await msg.answer(f"⚠️ Ошибка при запросе API: {response.text}")
            return

        report = response.json()

        text = (
            f"📊 *Dashly — отчёт за неделю*\n\n"
            f"💰 *Выручка:* {report['revenue']:,} ₽\n"
            f"📦 *Заказы:* {report['orders']}\n"
            f"💳 *Средний чек:* {report['avg_check']:.0f} ₽\n"
            f"💸 *Комиссия:* {report['commission']:,} ₽\n"
            f"🏦 *Прибыль:* {report['profit']:,} ₽\n\n"
            f"*ТОП-5 товаров:*\n"
        )

        for i, item in enumerate(report["top5"], 1):
            text += f"{i}. {item['title']} — {item['qty']} шт ({item['revenue_pct']:.1f}% выручки)\n"

        if report.get("tips"):
            text += "\n*Советы:*\n"
            for tip in report["tips"]:
                text += f"💡 {tip}\n"


        image_bytes = base64.b64decode(report["chart_png_base64"])
        image_file = types.BufferedInputFile(image_bytes, filename="chart.png")

        await msg.answer_photo(
            photo=image_file,
            caption=text,
            parse_mode="Markdown",
        )

    except Exception as e:
        await msg.answer(f"❌ Произошла ошибка: {e}")


async def main():
    bot = Bot(token="8022350360:AAF2zifWihlUoYz0q_GQ1xPCHKJ0vA-hvVQ")
    dp = Dispatcher()
    dp.include_router(router)

    print("🤖 DashlyBot запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
