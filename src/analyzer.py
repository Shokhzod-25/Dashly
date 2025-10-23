import asyncio
import io
import pandas as pd
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from src.dashboard import generate_dashboard_chart_async
from src.data import col_map_candidates, platform
import matplotlib

matplotlib.use("Agg")


DEFAULT_COMMISSION = 0.15
CHUNK_SIZE = 10000
ANOMALY_THRESHOLD = 0.3


async def _read_table_async(content: bytes, filename: str) -> pd.DataFrame:

    def _blocking_read():
        name = filename.lower()
        buf = io.BytesIO(content)
        df = None

        if len(content) > 5 * 1024 * 1024:
            if name.endswith(".csv"):
                chunks = []
                try:
                    for chunk in pd.read_csv(
                        buf, sep=None, engine="python", chunksize=CHUNK_SIZE
                    ):
                        chunks.append(chunk)
                    df = pd.concat(chunks, ignore_index=True)
                except Exception:
                    buf.seek(0)
                    chunks = []
                    for chunk in pd.read_csv(buf, sep=";", chunksize=CHUNK_SIZE):
                        chunks.append(chunk)
                    df = pd.concat(chunks, ignore_index=True)
            elif name.endswith((".xls", ".xlsx")):
                buf.seek(0)
                df = pd.read_excel(buf)
            else:
                raise ValueError(
                    "Неподдерживаемый тип файла. Используйте CSV или XLSX."
                )
        else:
            if name.endswith(".csv"):
                df = read_csv_safe(buf=buf)
            elif name.endswith((".xls", ".xlsx")):
                buf.seek(0)
                df = pd.read_excel(buf)
            else:
                raise ValueError(
                    "Неподдерживаемый тип файла. Используйте CSV или XLSX."
                )

        return df

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        df = await loop.run_in_executor(executor, _blocking_read)

    return df

def read_csv_safe(buf: io.BytesIO) -> pd.DataFrame:
    buf.seek(0)
    try:
        df = pd.read_csv(buf, sep=";", encoding="utf-8")
    except UnicodeDecodeError:
        buf.seek(0)
        df = pd.read_csv(buf, sep=";", encoding="cp1251")
    return df

def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: c.strip().lower() for c in df.columns})

    rename_map = {}
    for target, candidates in col_map_candidates.items():
        for c in candidates:
            if c in df.columns:
                rename_map[c] = target
                break
    if rename_map:
        df = df.rename(columns=rename_map)

    if "date" not in df.columns:
        raise ValueError("Отсутствует обязательный столбец: date")
    if "sku" not in df.columns and "title" not in df.columns:
        raise ValueError("Отсутствует обязательный столбец: sku или title")
    if "qty" not in df.columns:
        raise ValueError("Отсутствует обязательный столбец: quantity/qtyqty.")

    if "revenue" not in df.columns:
        if "price" in df.columns:
            df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)
            df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0).astype(int)
            df["revenue"] = df["price"] * df["qty"]
        else:
            df["revenue"] = 0.0

    if "commission_pct" not in df.columns:
        df["commission_pct"] = DEFAULT_COMMISSION
    else:
        df["commission_pct"] = pd.to_numeric(
            df["commission_pct"], errors="coerce"
        ).fillna(DEFAULT_COMMISSION)

    if "platform" not in df.columns:
        df["platform"] = "Unknown"
    else:
        df["platform"] = df["platform"].astype(str).str.strip()
        df["platform"] = df["platform"].replace(platform)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if df["date"].isnull().any():
        raise ValueError(
            "Некоторые данные не удалось проанализировать — проверьте формат данных."
        )
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0).astype(int)
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0.0)

    if "title" not in df.columns:
        df["title"] = df.get("sku").astype(str)

    return df


def _period_bounds(
    df: pd.DataFrame,
    period: str,
    custom_start: Optional[str] = None,
    custom_end: Optional[str] = None,
) -> Tuple[pd.Timestamp, pd.Timestamp]:
    last = df["date"].max().normalize()

    if period == "custom":
        if not custom_start or not custom_end:
            raise ValueError(
                "custom_start и custom_end требуются для настраиваемого периода"
            )
        start = pd.to_datetime(custom_start).normalize()
        end = pd.to_datetime(custom_end).normalize()

        if start > end:
            raise ValueError("custom_start должен быть перед custom_end")
        if end > last:
            end = last

        return start, end

    elif period == "today":
        return last, last

    elif period == "week":
        start = last - pd.Timedelta(days=6)
        return start, last

    elif period == "month":
        start = last - pd.Timedelta(days=29)
        return start, last

    elif period == "all":
        start = df["date"].min().normalize()
        return start, last

    else:
        raise ValueError("Неподдерживаемый период")


def _detect_anomalies(daily_data: pd.Series) -> List[Dict]:
    anomalies = []

    if len(daily_data) < 2:
        return anomalies

    pct_change = daily_data.pct_change() * 100

    for i in range(1, len(daily_data)):
        change = pct_change.iloc[i]

        if pd.isna(change) or daily_data.iloc[i - 1] == 0:
            continue

        if abs(change) > ANOMALY_THRESHOLD * 100:
            anomaly_type = "spike" if change > 0 else "drop"
            anomalies.append(
                {
                    "date": daily_data.index[i].strftime("%Y-%m-%d"),
                    "type": str(anomaly_type),
                    "change_pct": float(round(change, 1)),
                    "value": float(round(daily_data.iloc[i], 2)),
                }
            )

    return anomalies


def _analyze_by_platform(df_period: pd.DataFrame) -> Dict:
    if "platform" not in df_period.columns:
        return {}

    platform_stats = (
        df_period.groupby("platform")
        .agg({"revenue": "sum", "qty": "sum"})
        .to_dict("index")
    )

    total_revenue = float(df_period["revenue"].sum())

    result = {}
    for platform, stats in platform_stats.items():
        result[str(platform)] = {
            "revenue": float(stats["revenue"]),
            "orders": int(stats["qty"]),
            "revenue_pct": float(
                round(
                    (
                        (stats["revenue"] / total_revenue * 100)
                        if total_revenue > 0
                        else 0
                    ),
                    1,
                )
            ),
        }

    return result


def _calc_metrics(df_period: pd.DataFrame):
    revenue = df_period["revenue"].sum()
    orders = df_period["qty"].sum()
    avg_check = (revenue / orders) if orders else 0.0
    commission = (df_period["revenue"] * df_period["commission_pct"]).sum()
    profit = revenue - commission

    return {
        "revenue": float(revenue),
        "orders": int(orders),
        "avg_check": float(avg_check),
        "commission": float(commission),
        "profit": float(profit),
    }


def _pct_change(curr, prev):
    if prev == 0:
        return None
    return round((curr - prev) / prev * 100, 2)


def _top5(df_period: pd.DataFrame):
    grp = (
        df_period.groupby(["sku", "title"], as_index=False)
        .agg({"qty": "sum", "revenue": "sum"})
        .sort_values("qty", ascending=False)
    )
    total_revenue = float(grp["revenue"].sum()) or 1.0
    top = []
    for _, row in grp.head(5).iterrows():
        top.append(
            {
                "sku": str(row["sku"]),
                "title": str(row["title"]),
                "qty": int(row["qty"]),
                "revenue": float(row["revenue"]),
                "revenue_pct": float(round(row["revenue"] / total_revenue * 100, 2)),
            }
        )
    return top


def _generate_tips(
    metrics_curr: Dict,
    metrics_prev: Dict | None,
    top5_curr: List[Dict],
    prev_top5: List[Dict],
    anomalies: List[Dict],
    platform_stats: Dict,
) -> List[str]:
    tips = []

    if anomalies:
        for anomaly in anomalies[:2]:
            change = abs(anomaly["change_pct"])
            if anomaly["type"] == "drop":
                tips.append(f"⚠️ Резкое падение {anomaly['date']}: {change}%")
            else:
                tips.append(f"🚀 Резкий рост {anomaly['date']}: +{change}%")

    if metrics_prev and metrics_curr.get("revenue") and metrics_prev.get("revenue"):
        revenue_pct = _pct_change(metrics_curr["revenue"], metrics_prev["revenue"])
        if revenue_pct is not None:
            if revenue_pct > 10:
                tips.append(
                    f"🚀 Продажи выросли на {revenue_pct}% — отличный результат!"
                )
            elif revenue_pct < -10:
                tips.append(
                    f"⚠️ Продажи снизились на {abs(revenue_pct)}% — проверь рекламу."
                )

    if top5_curr and top5_curr[0]["revenue_pct"] > 40:
        tips.append(
            f"📦 Топ-товар {top5_curr[0]['title']} приносит {top5_curr[0]['revenue_pct']}% выручки — увеличь запасы."
        )

    if metrics_prev and metrics_curr.get("avg_check") and metrics_prev.get("avg_check"):
        avg_check_pct = _pct_change(
            metrics_curr["avg_check"], metrics_prev["avg_check"]
        )
        if avg_check_pct is not None and avg_check_pct < -5:
            tips.append(
                f"💰 Средний чек снизился на {abs(avg_check_pct)}% — добавь сопутствующие товары."
            )

    if metrics_curr.get("commission_pct", 0) > 15:
        tips.append(
            f"💸 Комиссия достигла {metrics_curr['commission_pct']}% — пересмотри категории или условия."
        )

    prev_skus = {p["sku"] for p in (prev_top5 or [])}
    for p in top5_curr or []:
        if p["sku"] not in prev_skus:
            tips.append(f"🔥 Новый лидер: {p['title']}.")
            break

    if platform_stats and len(platform_stats) > 1:
        sorted_platforms = sorted(
            platform_stats.items(), key=lambda x: x[1].get("revenue", 0), reverse=True
        )
        best_platform = sorted_platforms[0]
        tips.append(
            f"🏆 Лучшая платформа: {best_platform[0]} "
            f"({best_platform[1].get('revenue_pct', 0)}% выручки)"
        )

    if not tips:
        tips.append("✅ Показатели стабильны — продолжайте в том же духе.")

    return tips


async def analyze_file_async(
    content: bytes,
    filename: str,
    period: str,
    custom_start: Optional[str] = None,
    custom_end: Optional[str] = None,
):
    df = await _read_table_async(content, filename)
    df = _ensure_columns(df)

    start, end = _period_bounds(df, period, custom_start, custom_end)
    mask = (df["date"].dt.normalize() >= start) & (df["date"].dt.normalize() <= end)
    df_curr = df.loc[mask].copy()

    if df_curr.empty:
        raise ValueError("Нет данных за запрошенный период")

    delta = end - start
    prev_start = start - delta - pd.Timedelta(days=1)
    prev_end = start - pd.Timedelta(days=1)
    mask_prev = (df["date"].dt.normalize() >= prev_start) & (
        df["date"].dt.normalize() <= prev_end
    )
    df_prev = df.loc[mask_prev].copy()

    metrics_curr = _calc_metrics(df_curr)
    metrics_prev = _calc_metrics(df_prev) if not df_prev.empty else None

    if metrics_prev:
        metrics_curr["revenue_change_pct"] = _pct_change(
            metrics_curr["revenue"], metrics_prev["revenue"]
        )
        metrics_curr["orders_change_pct"] = _pct_change(
            metrics_curr["orders"], metrics_prev["orders"]
        )
        metrics_curr["avg_check_change_pct"] = _pct_change(
            metrics_curr["avg_check"], metrics_prev["avg_check"]
        )
    else:
        metrics_curr["revenue_change_pct"] = None
        metrics_curr["orders_change_pct"] = None
        metrics_curr["avg_check_change_pct"] = None

    top5_curr = _top5(df_curr)
    top5_prev = _top5(df_prev) if not df_prev.empty else []

    daily_revenue = df_curr.groupby(df_curr["date"].dt.normalize())["revenue"].sum()
    anomalies = _detect_anomalies(daily_revenue)

    platform_stats = _analyze_by_platform(df_curr)

    tips = _generate_tips(
        metrics_curr, metrics_prev, top5_curr, top5_prev, anomalies, platform_stats
    )

    chart = await generate_dashboard_chart_async(df_curr, metrics_curr)

    return {
        "metrics": metrics_curr,
        "top5": top5_curr,
        "tips": tips,
        "anomalies": anomalies,
        "platform_stats": platform_stats,
        "chart_png": chart,
        "meta": {
            "source": "CSV",
            "mode": "manual",
            "period": period,
            "period_start": start.strftime("%Y-%m-%d"),
            "period_end": end.strftime("%Y-%m-%d"),
            "rows_processed": int(len(df)),
            "has_anomalies": bool(len(anomalies) > 0),
        },
    }
