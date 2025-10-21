Сделал — создал в документе готовый шаблон API (FastAPI) для MVP без Telegram.

# Dashly API — FastAPI MVP

Ниже — готовый шаблон бэкенда (FastAPI) для MVP **без** Telegram-бота. Включено:

* `POST /analyze` — принимает CSV/XLSX и параметр `period` (`today` или `week`) и возвращает JSON с метриками + PNG-график (base64).
* `GET /health` — простая проверка.
* Swagger/OpenAPI (автоматически от FastAPI).
* Dockerfile + docker-compose.yml.
* `.env.example` и README.
* Демо CSV-файлы `demo_wb.csv`, `demo_ozon.csv`.

---

## Файловая структура (в репозитории)

```
dashly-api/
├─ app/
│  ├─ main.py
│  ├─ analyzer.py
│  └─ utils.py
├─ demo_wb.csv
├─ demo_ozon.csv
├─ requirements.txt
├─ Dockerfile
├─ docker-compose.yml
├─ .env.example
└─ README.md
```

---

## app/main.py

```python
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import base64
from analyzer import analyze_file

app = FastAPI(title="Dashly API (MVP)")

@app.get('/health')
def health():
    return {"status": "ok"}

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


@app.post('/analyze', response_model=AnalyzeResponse)
async def analyze(period: str = Form(...), file: UploadFile = File(...)):
    """period: 'today' or 'week' ("month","all" are PRO and currently locked)
    Accepts CSV or XLSX file.
    Returns metrics + PNG chart (base64 encoded).
    """
    period = period.lower()
    if period not in ('today', 'week', 'month', 'all'):
        raise HTTPException(status_code=400, detail='period must be one of: today, week, month, all')
    if period in ('month', 'all'):
        raise HTTPException(status_code=403, detail='Feature locked: month/all are PRO')

    content = await file.read()
    try:
        result = analyze_file(content, filename=file.filename, period=period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # chart is bytes; encode to base64
    chart_b64 = base64.b64encode(result['chart_png']).decode('ascii')
    response = {
        'revenue': result['metrics']['revenue'],
        'orders': int(result['metrics']['orders']),
        'avg_check': result['metrics']['avg_check'],
        'commission': result['metrics']['commission'],
        'profit': result['metrics']['profit'],
        'revenue_change_pct': result['metrics'].get('revenue_change_pct'),
        'orders_change_pct': result['metrics'].get('orders_change_pct'),
        'avg_check_change_pct': result['metrics'].get('avg_check_change_pct'),
        'top5': result['top5'],
        'tips': result['tips'],
        'chart_png_base64': chart_b64,
        'meta': result['meta'],
    }
    return JSONResponse(content=response)
```

---

## app/analyzer.py

```python
import io
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

DEFAULT_COMMISSION = 0.15


def _read_table(content: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith('.csv'):
        df = pd.read_csv(io.BytesIO(content))
    elif name.endswith(('.xls', '.xlsx')):
        df = pd.read_excel(io.BytesIO(content))
    else:
        raise ValueError('Unsupported file type. Use CSV or XLSX')
    return df


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Normalize column names
    df = df.rename(columns={c: c.strip().lower() for c in df.columns})
    required = ['date', 'sku', 'title', 'qty', 'revenue']
    for r in required:
        if r not in df.columns:
            raise ValueError(f'Missing required column: {r}')
    # commission_pct optional
    if 'commission_pct' not in df.columns:
        df['commission_pct'] = DEFAULT_COMMISSION
    else:
        # fill missing commission with default
        df['commission_pct'] = df['commission_pct'].fillna(DEFAULT_COMMISSION)
    # parse date
    df['date'] = pd.to_datetime(df['date'])
    df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0).astype(int)
    df['revenue'] = pd.to_numeric(df['revenue'], errors='coerce').fillna(0.0)
    return df


def _period_bounds(df: pd.DataFrame, period: str):
    # Use data's max date as "now" anchor
    last = df['date'].max().normalize()
    if period == 'today':
        start = last
        end = last
    elif period == 'week':
        start = last - pd.Timedelta(days=6)  # last 7 days
        end = last
    else:
        raise ValueError('Unsupported period for free API')
    return start, end


def _calc_metrics(df_period: pd.DataFrame):
    revenue = df_period['revenue'].sum()
    orders = df_period['qty'].sum()
    avg_check = (revenue / orders) if orders else 0.0
    commission = (df_period['revenue'] * df_period['commission_pct']).sum()
    profit = revenue - commission
    return {
        'revenue': float(round(revenue, 2)),
        'orders': int(orders),
        'avg_check': float(round(avg_check, 2)),
        'commission': float(round(commission, 2)),
        'profit': float(round(profit, 2)),
    }


def _pct_change(curr, prev):
    if prev == 0:
        return None
    return round((curr - prev) / prev * 100, 2)


def _top5(df_period: pd.DataFrame):
    grp = df_period.groupby(['sku', 'title'], as_index=False).agg({'qty': 'sum', 'revenue': 'sum'})
    grp = grp.sort_values('qty', ascending=False)
    total_revenue = grp['revenue'].sum() or 1
    top = []
    for i, row in grp.head(5).iterrows():
        top.append({'sku': row['sku'], 'title': row['title'], 'qty': int(row['qty']), 'revenue': float(round(row['revenue'],2)), 'revenue_pct': round(row['revenue']/total_revenue*100,2)})
    return top


def _generate_chart(df_period: pd.DataFrame):
    daily = df_period.groupby(df_period['date'].dt.normalize()).agg({'revenue': 'sum'}).reindex(pd.date_range(df_period['date'].min().normalize(), df_period['date'].max().normalize(), freq='D'), fill_value=0)
    x = daily.index
    y = daily['revenue'].values
    fig, ax = plt.subplots(figsize=(8,3), dpi=100)
    fig.patch.set_facecolor('white')
    ax.plot(x, y, linewidth=2, color='#0056b3')
    ax.set_xlabel('Date')
    ax.set_ylabel('Revenue')
    ax.grid(axis='y', linestyle='--', alpha=0.3)
    fig.autofmt_xdate()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _generate_tips(metrics_curr, metrics_prev, top5_curr, prev_top5):
    tips = []
    # revenue drop
    if metrics_prev and metrics_curr['revenue'] is not None and metrics_prev.get('revenue') is not None:
        pct = _pct_change(metrics_curr['revenue'], metrics_prev['revenue'])
        if pct is not None and pct < -15:
            tips.append(f"⚠️ Продажи упали на {abs(pct)}% — проверь активность рекламы.")
    # one product >40% revenue
    if top5_curr:
        if top5_curr[0]['revenue_pct'] > 40:
            tips.append(f"📦 Основная выручка от {top5_curr[0]['title']} — возможна зависимость.")
    # avg check down while orders up
    if metrics_prev and metrics_prev.get('orders') is not None:
        if metrics_curr['avg_check'] < metrics_prev.get('avg_check', 0) and metrics_curr['orders'] > metrics_prev.get('orders', 0):
            tips.append('💰 Скидки/акции снизили средний чек.')
    # new product in top5
    prev_skus = {p['sku'] for p in (prev_top5 or [])}
    for p in top5_curr:
        if p['sku'] not in prev_skus:
            tips.append(f"🔥 Новый лидер: {p['title']}.")
            break
    if not tips:
        tips.append('✅ Показатели стабильны — продолжайте в том же духе.')
    return tips


def analyze_file(content: bytes, filename: str, period: str):
    df = _read_table(content, filename)
    df = _ensure_columns(df)
    start, end = _period_bounds(df, period)
    mask = (df['date'].dt.normalize() >= start) & (df['date'].dt.normalize() <= end)
    df_curr = df.loc[mask].copy()
    if df_curr.empty:
        raise ValueError('No data in the requested period')

    # previous period
    delta = (end - start)
    prev_start = start - delta - pd.Timedelta(days=1) + pd.Timedelta(days=0)
    prev_end = start - pd.Timedelta(days=1)
    mask_prev = (df['date'].dt.normalize() >= prev_start) & (df['date'].dt.normalize() <= prev_end)
    df_prev = df.loc[mask_prev].copy()

    metrics_curr = _calc_metrics(df_curr)
    metrics_prev = _calc_metrics(df_prev) if not df_prev.empty else None

    # add pct changes
    if metrics_prev:
        metrics_curr['revenue_change_pct'] = _pct_change(metrics_curr['revenue'], metrics_prev['revenue'])
        metrics_curr['orders_change_pct'] = _pct_change(metrics_curr['orders'], metrics_prev['orders'])
        metrics_curr['avg_check_change_pct'] = _pct_change(metrics_curr['avg_check'], metrics_prev['avg_check'])
    else:
        metrics_curr['revenue_change_pct'] = None
        metrics_curr['orders_change_pct'] = None
        metrics_curr['avg_check_change_pct'] = None

    top5_curr = _top5(df_curr)
    top5_prev = _top5(df_prev) if not df_prev.empty else []

    tips = _generate_tips(metrics_curr, metrics_prev, top5_curr, top5_prev)

    chart = _generate_chart(df_curr)

    return {
        'metrics': metrics_curr,
        'top5': top5_curr,
        'tips': tips,
        'chart_png': chart,
        'meta': {
            'source': 'CSV',
            'mode': 'manual',
            'period': period,
            'rows_processed': len(df),
        }
    }
```

---

## requirements.txt

```
fastapi
uvicorn[standard]
pandas
openpyxl
matplotlib
python-multipart
pydantic
```

---

## Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY ./requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY ./app /app/app
COPY demo_wb.csv /app/demo_wb.csv
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## docker-compose.yml

```yaml
version: '3.8'
services:
  dashly:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./:/app
    environment:
      - PYTHONUNBUFFERED=1
```

---

## .env.example

```
# example environment variables
APP_ENV=development
```

---

## demo_wb.csv (пример)

```
date,sku,title,qty,revenue,commission_pct
2025-10-14,SKU1,Белая футболка,20,5000,0.15
2025-10-15,SKU2,Кроссовки,15,30000,0.12
2025-10-16,SKU1,Белая футболка,10,2500,0.15
2025-10-17,SKU3,Шапка,5,2500,
2025-10-18,SKU2,Кроссовки,20,40000,0.12
2025-10-19,SKU4,Куртка,2,20000,0.18
2025-10-20,SKU5,Шорты,3,4500,
```

---

## README.md (короткая инструкция)

````markdown
# Dashly API — FastAPI MVP

Запуск (локально):

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
````

Откройте [http://localhost:8000/docs](http://localhost:8000/docs) — Swagger UI.

Пример запроса (curl):

```bash
curl -X POST "http://localhost:8000/analyze" -F "period=week" -F "file=@demo_wb.csv"
```

Docker:

```bash
docker-compose up --build
```

```

---

Если нужно — могу:

- подготовить готовый GitHub-репозиторий и запушить код (требуется доступ или я подготовлю архив),
- добавить unit-tests (pytest),
- прикрутить Sentry/логирование, или
- расширить API (поддержка `month`/`all`, авторизация, хранение отчетов).

Выбирай, что делаем дальше.

```


Открой документ **"Dashly API — FastAPI MVP"** (в панели справа) — там всё: `main.py`, `analyzer.py`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`, demo CSV и README.

Что могу сделать дальше (выбери):

1. Подготовить ZIP / Git-репозиторий (и дать архив).
2. Добавить unit-tests (pytest) и CI.
3. Расширить эндпоинт `/analyze` — поддержать `month`/`all` и хранение отчётов.
4. Подготовить пример запроса для Botmother (webhook) или интеграцию.

Скажи номер пункта или «сделай всё» — выполню следующий шаг.
