import base64
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse

from src.analyzer import analyze_file
from src.schemas import AnalyzeResponse

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(period: str = Form(...), file: UploadFile = File(...)):
    period = period.lower()
    if period not in ("today", "week", "month", "all"):
        raise HTTPException(
            status_code=400, detail="period must be one of: today, week, month, all"
        )
    if period in ("month", "all"):
        raise HTTPException(status_code=403, detail="Feature locked: month/all are PRO")

    content = await file.read()
    try:
        result = analyze_file(content, filename=file.filename, period=period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    chart_b64 = base64.b64encode(result["chart_png"]).decode("ascii")
    response = {
        "revenue": result["metrics"]["revenue"],
        "orders": int(result["metrics"]["orders"]),
        "avg_check": result["metrics"]["avg_check"],
        "commission": result["metrics"]["commission"],
        "profit": result["metrics"]["profit"],
        "revenue_change_pct": result["metrics"].get("revenue_change_pct"),
        "orders_change_pct": result["metrics"].get("orders_change_pct"),
        "avg_check_change_pct": result["metrics"].get("avg_check_change_pct"),
        "top5": result["top5"],
        "tips": result["tips"],
        "chart_png_base64": chart_b64,
        "meta": result["meta"],
    }
    return JSONResponse(content=response)
