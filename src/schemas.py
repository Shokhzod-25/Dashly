from pydantic import BaseModel, Field


class AnalyzeResponse(BaseModel):
    class Config:
        json_schema_extra = {
            "example": {
                "chart_png_base64": "iVBORw0KGgoAAAANSUhEUg...",
                "text_report": "Оформленный отчет"
            }
        }
