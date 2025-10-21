from pydantic import BaseModel


class AnalyzeResponse(BaseModel):
    revenue: float
    orders: int
    avg_check: float
    commission: float
    profit: float
    revenue_change_pct: float | None
    orders_change_pct: float | None
    avg_check_change_pct: float | None
    top5: list
    tips: list
    chart_png_base64: str
    meta: dict
