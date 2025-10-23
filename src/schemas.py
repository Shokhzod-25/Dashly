from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class Product(BaseModel):
    """Товар в ТОП-5"""

    sku: str = Field(..., description="Артикул товара")
    title: str = Field(..., description="Название товара")
    qty: int = Field(..., description="Количество проданных единиц")
    revenue: float = Field(..., description="Выручка от товара")
    revenue_pct: float = Field(..., description="Процент от общей выручки")


class Anomaly(BaseModel):
    """Аномалия в данных"""

    date: str = Field(..., description="Дата аномалии (YYYY-MM-DD)")
    type: str = Field(..., description="Тип аномалии: 'spike' или 'drop'")
    change_pct: float = Field(..., description="Процент изменения")
    value: float = Field(..., description="Значение метрики")


class PlatformStats(BaseModel):
    """Статистика по платформе"""

    revenue: float = Field(..., description="Выручка")
    orders: int = Field(..., description="Количество заказов")
    revenue_pct: float = Field(..., description="Процент от общей выручки")


class MetaInfo(BaseModel):
    """Метаданные отчёта"""

    source: str = Field(..., description="Источник данных")
    mode: str = Field(..., description="Режим работы")
    period: str = Field(..., description="Период анализа")
    period_start: str = Field(..., description="Начало периода")
    period_end: str = Field(..., description="Конец периода")
    rows_processed: int = Field(..., description="Обработано строк")
    has_anomalies: bool = Field(..., description="Обнаружены аномалии")


class AnalyzeResponse(BaseModel):
    """Ответ API /analyze"""

    revenue: float = Field(..., description="Выручка", example=122000.0)
    orders: int = Field(..., description="Количество заказов", example=356)
    avg_check: float = Field(..., description="Средний чек", example=343.0)
    commission: float = Field(..., description="Комиссия", example=18300.0)
    profit: float = Field(..., description="Прибыль", example=103700.0)

    # Изменения относительно прошлого периода
    revenue_change_pct: Optional[float] = Field(
        None, description="Изменение выручки (%)", example=-15.0
    )
    orders_change_pct: Optional[float] = Field(
        None, description="Изменение заказов (%)", example=-8.0
    )
    avg_check_change_pct: Optional[float] = Field(
        None, description="Изменение среднего чека (%)", example=-7.0
    )

    # ТОП-5 товаров
    top5: List[Product] = Field(..., description="Топ-5 товаров по количеству")

    # Советы
    tips: List[str] = Field(..., description="Аналитические советы")

    # Аномалии (NEW)
    anomalies: List[Anomaly] = Field(default=[], description="Обнаруженные аномалии")

    # Статистика по платформам (NEW)
    platform_stats: Dict[str, PlatformStats] = Field(
        default={}, description="Распределение по платформам"
    )

    # График
    chart_png_base64: str = Field(..., description="PNG-график в base64")

    # Метаданные
    meta: MetaInfo = Field(..., description="Метаданные отчёта")

    class Config:
        json_schema_extra = {
            "example": {
                "revenue": 122000.0,
                "orders": 356,
                "avg_check": 343.0,
                "commission": 18300.0,
                "profit": 103700.0,
                "revenue_change_pct": -15.0,
                "orders_change_pct": -8.0,
                "avg_check_change_pct": -7.0,
                "top5": [
                    {
                        "sku": "WB123",
                        "title": "Футболка белая",
                        "qty": 120,
                        "revenue": 39040.0,
                        "revenue_pct": 32.0,
                    }
                ],
                "tips": [
                    "⚠️ Продажи упали на 15% — проверь активность рекламы.",
                    "🏆 Лучшая платформа: Wildberries (65% выручки)",
                ],
                "anomalies": [
                    {
                        "date": "2025-08-15",
                        "type": "drop",
                        "change_pct": -35.2,
                        "value": 8500.0,
                    }
                ],
                "platform_stats": {
                    "Wildberries": {
                        "revenue": 79300.0,
                        "orders": 231,
                        "revenue_pct": 65.0,
                    },
                    "Ozon": {"revenue": 42700.0, "orders": 125, "revenue_pct": 35.0},
                },
                "chart_png_base64": "iVBORw0KGgoAAAANSUhEUg...",
                "meta": {
                    "source": "CSV",
                    "mode": "manual",
                    "period": "week",
                    "period_start": "2025-08-01",
                    "period_end": "2025-08-07",
                    "rows_processed": 50,
                    "has_anomalies": True,
                },
            }
        }
