import base64
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime

from src.analyzer import analyze_file_async
from src.schemas import AnalyzeResponse
import aiohttp

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


def _generate_text_report(result: dict) -> str:
    def format_currency(value):
        return f"{value:,.0f} ₽".replace(",", " ")

    def format_number(value):
        return f"{value:,}".replace(",", " ")

    report_lines = [
        "✨ *DASHLY ОТЧЕТ* ✨",
        "",
        "*Основные показатели:*",
        f"💰 Выручка: `{format_currency(result['metrics']['revenue'])}`",
        f"📦 Заказы: `{format_number(int(result['metrics']['orders']))}`",
        f"💳 Средний чек: `{format_currency(result['metrics']['avg_check'])}`",
        f"💵 Прибыль: `{format_currency(result['metrics']['profit'])}`",
        "",
    ]

    # Динамика метрик
    changes = []

    revenue_change = result["metrics"].get("revenue_change_pct")
    if revenue_change is not None:
        trend_icon = "🟢" if revenue_change >= 0 else "🔴"
        changes.append(f"Выручка: {trend_icon} {revenue_change:+.1f}%")

    orders_change = result["metrics"].get("orders_change_pct")
    if orders_change is not None:
        trend_icon = "🟢" if orders_change >= 0 else "🔴"
        changes.append(f"Заказы: {trend_icon} {orders_change:+.1f}%")

    avg_check_change = result["metrics"].get("avg_check_change_pct")
    if avg_check_change is not None:
        trend_icon = "🟢" if avg_check_change >= 0 else "🔴"
        changes.append(f"Ср.чек: {trend_icon} {avg_check_change:+.1f}%")

    if changes:
        report_lines.append("*Динамика к прошлому периоду:*")
        for change in changes:
            report_lines.append(change)
        report_lines.append("")

    # Топ товары (ИСПРАВЛЕННАЯ ЧАСТЬ)
    if result.get("top5"):
        report_lines.append("*Топ-5 товаров:*")
        for i, item in enumerate(result["top5"][:5], 1):
            # Безопасное получение названия товара
            title = item.get("title", item.get("sku", "Неизвестный товар"))
            qty = item.get("qty", 0)
            revenue_pct = item.get("revenue_pct", 0)
            report_lines.append(f"{i}. {title} - {qty} шт. ({revenue_pct:.1f}%)")
        report_lines.append("")

    # Рекомендации (ИСПРАВЛЕННАЯ ЧАСТЬ)
    tips = result.get("tips", [])
    if tips:
        report_lines.append("*Рекомендации:*")
        for i, tip in enumerate(tips, 1):
            report_lines.append(f"{i}. {tip}")
    else:
        report_lines.append("*Рекомендации:*")
        report_lines.append("1. Показатели стабильны — продолжайте в том же духе!")

    # Футер
    report_lines.extend(["", f"_Отчет от {datetime.now().strftime('%d.%m.%Y %H:%M')}_"])

    return "\n".join(report_lines)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    period: str = Form(...),
    file_url: str = Form(...),
    custom_start: Optional[str] = Form(None),
    custom_end: Optional[str] = Form(None),
):
    period = period.lower()
    print("period:", period)
    print("file_url:", file_url)

    if period not in ("today", "week", "custom"):
        raise HTTPException(
            status_code=400,
            detail="период должен быть одним из: today, week, month, all, custom",
        )

    if period == "custom":
        if not custom_start or not custom_end:
            raise HTTPException(
                status_code=400,
                detail="custom_start и custom_end требуются для настраиваемого периода",
            )
        try:
            datetime.strptime(custom_start, "%Y-%m-%d")
            datetime.strptime(custom_end, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Даты должны быть в формате ГГГГ-ММ-ДД."
            )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as resp:
                if resp.status != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Не удалось загрузить файл. Код: {resp.status}",
                    )
                content = await resp.read()

                content_disp = resp.headers.get("Content-Disposition", "")
                if "filename=" in content_disp:
                    filename = content_disp.split("filename=")[-1].strip('"')
                else:
                    filename = file_url.split("/")[-1] or "downloaded_file.csv"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки файла: {str(e)}")

    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail="Файл слишком большой. Максимальный размер: 50 МБ."
        )

    if not filename.lower().endswith(".csv"):
        print("⚠️ Предупреждение: имя файла без .csv, продолжаем как CSV")

    try:
        result = await analyze_file_async(
            content,
            filename=filename,
            period=period,
            custom_start=custom_start,
            custom_end=custom_end,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Внутренняя ошибка во время анализа: {str(e)}"
        )

    chart_b64 = base64.b64encode(result["chart_png"]).decode("ascii")
    text_report = _generate_text_report(result)

    return JSONResponse(
        content={
            "chart_png_base64": chart_b64,
            "text_report": text_report,
        }
    )
