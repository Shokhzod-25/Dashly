import io
import pandas as pd
import matplotlib.pyplot as plt
import io
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np

DEFAULT_COMMISSION = 0.15


def _read_table(content: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    buf = io.BytesIO(content)
    if name.endswith(".csv"):
        try:
            df = pd.read_csv(buf, sep=None, engine="python")
        except Exception:
            buf.seek(0)
            df = pd.read_csv(buf, sep=";")
    elif name.endswith((".xls", ".xlsx")):
        buf.seek(0)
        df = pd.read_excel(buf)
    else:
        raise ValueError("Unsupported file type. Use CSV or XLSX")
    return df


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: c.strip().lower() for c in df.columns})

    col_map_candidates = {
        "date": ["date", "order_date", "dt"],
        "sku": ["sku", "product_sku", "article"],
        "title": ["title", "product_name", "name"],
        "qty": ["qty", "quantity", "count", "amount"],
        "price": ["price", "unit_price"],
        "revenue": ["revenue", "total", "sum"],
        "commission_pct": ["commission_pct", "commission", "commission_rate"],
    }

    rename_map = {}
    for target, candidates in col_map_candidates.items():
        for c in candidates:
            if c in df.columns:
                rename_map[c] = target
                break
    if rename_map:
        df = df.rename(columns=rename_map)

    if "date" not in df.columns:
        raise ValueError("Missing required column: date")
    if "sku" not in df.columns and "title" not in df.columns:
        raise ValueError("Missing required column: sku or title")
    if "qty" not in df.columns:
        raise ValueError("Missing required column: quantity/qty")

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

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if df["date"].isnull().any():
        raise ValueError("Some dates could not be parsed — check date format")
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0).astype(int)
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0.0)

    if "title" not in df.columns:
        df["title"] = df.get("sku").astype(str)

    return df


def _period_bounds(df: pd.DataFrame, period: str):
    last = df["date"].max().normalize()
    if period == "today":
        start = last
        end = last
    elif period == "week":
        start = last - pd.Timedelta(days=6)
        end = last
    else:
        raise ValueError("Unsupported period for free API")
    return start, end


def _calc_metrics(df_period: pd.DataFrame):
    revenue = df_period["revenue"].sum()
    orders = df_period["qty"].sum()
    avg_check = (revenue / orders) if orders else 0.0
    commission = (df_period["revenue"] * df_period["commission_pct"]).sum()
    profit = revenue - commission
    return {
        "revenue": float(round(revenue, 2)),
        "orders": int(orders),
        "avg_check": float(round(avg_check, 2)),
        "commission": float(round(commission, 2)),
        "profit": float(round(profit, 2)),
    }


def _pct_change(curr, prev):
    if prev == 0:
        return None
    return round((curr - prev) / prev * 100, 2)


def _top5(df_period: pd.DataFrame):
    grp = df_period.groupby(["sku", "title"], as_index=False).agg(
        {"qty": "sum", "revenue": "sum"}
    )
    grp = grp.sort_values("qty", ascending=False)
    total_revenue = grp["revenue"].sum() or 1
    top = []
    for i, row in grp.head(5).iterrows():
        top.append(
            {
                "sku": row["sku"],
                "title": row["title"],
                "qty": int(row["qty"]),
                "revenue": float(round(row["revenue"], 2)),
                "revenue_pct": round(row["revenue"] / total_revenue * 100, 2),
            }
        )
    return top


def _generate_dashboard_chart(df_period: pd.DataFrame, metrics: dict):
    """
    Генерирует премиум PNG-дашборд с графиком динамики продаж
    в стиле современных аналитических платформ
    """
    # Подготовка данных для графика
    daily = (
        df_period.groupby(df_period["date"].dt.normalize())
        .agg({"revenue": "sum", "qty": "sum"})
        .reindex(
            pd.date_range(
                df_period["date"].min().normalize(),
                df_period["date"].max().normalize(),
                freq="D",
            ),
            fill_value=0,
        )
    )

    x = daily.index
    y_revenue = daily["revenue"].values
    y_orders = daily["qty"].values

    # Создание фигуры
    fig = plt.figure(figsize=(14, 8), dpi=150)
    fig.patch.set_facecolor("#f5f7fa")

    # Сетка: заголовок, график, метрики
    gs = gridspec.GridSpec(3, 1, height_ratios=[0.4, 2.2, 1.2], hspace=0.35)

    # ========== ЗАГОЛОВОК ==========
    ax_header = fig.add_subplot(gs[0])
    ax_header.axis("off")
    ax_header.set_xlim(0, 1)
    ax_header.set_ylim(0, 1)

    # Логотип/название
    ax_header.text(
        0.02,
        0.5,
        "DASHLY",
        fontsize=22,
        fontweight="bold",
        color="#0056b3",
        va="center",
        family="sans-serif",
    )

    # Подзаголовок
    period_text = "За последние 7 дней" if len(daily) > 1 else "Сегодня"
    ax_header.text(
        0.15,
        0.5,
        f"Аналитика продаж • {period_text}",
        fontsize=11,
        color="#6c757d",
        va="center",
        style="italic",
    )

    # Дата отчёта
    ax_header.text(
        0.98,
        0.5,
        f"Обновлено: {pd.Timestamp.now().strftime('%d.%m.%Y %H:%M')}",
        fontsize=9,
        color="#adb5bd",
        va="center",
        ha="right",
    )

    # ========== ГРАФИК ==========
    ax_main = fig.add_subplot(gs[1])
    ax_main.set_facecolor("#ffffff")

    # Градиентная заливка под графиком
    ax_main.fill_between(x, y_revenue, color="#0056b3", alpha=0.12)

    # Основная линия выручки с градиентом
    line = ax_main.plot(
        x,
        y_revenue,
        linewidth=3.5,
        color="#0056b3",
        label="Выручка",
        marker="o",
        markersize=7,
        markerfacecolor="#ffffff",
        markeredgecolor="#0056b3",
        markeredgewidth=2.5,
        zorder=3,
    )

    # Добавляем значения на пики
    if len(y_revenue) > 0:
        max_idx = np.argmax(y_revenue)
        if y_revenue[max_idx] > 0:
            ax_main.annotate(
                f"{y_revenue[max_idx]:,.0f} ₽",
                xy=(x[max_idx], y_revenue[max_idx]),
                xytext=(0, 15),
                textcoords="offset points",
                ha="center",
                fontsize=9,
                fontweight="bold",
                color="#0056b3",
                bbox=dict(
                    boxstyle="round,pad=0.5",
                    facecolor="white",
                    edgecolor="#0056b3",
                    linewidth=1.5,
                    alpha=0.95,
                ),
                zorder=4,
            )

    # Настройка внешнего вида
    ax_main.set_title(
        "Динамика выручки",
        fontsize=15,
        fontweight="600",
        color="#212529",
        pad=20,
        loc="left",
    )
    ax_main.set_xlabel("Дата", fontsize=10, color="#6c757d", fontweight="500")
    ax_main.set_ylabel("Выручка (₽)", fontsize=10, color="#6c757d", fontweight="500")

    # Сетка
    ax_main.grid(axis="y", linestyle="-", alpha=0.15, color="#dee2e6", linewidth=1)
    ax_main.grid(axis="x", linestyle="-", alpha=0.08, color="#dee2e6", linewidth=0.5)
    ax_main.spines["top"].set_visible(False)
    ax_main.spines["right"].set_visible(False)
    ax_main.spines["left"].set_color("#dee2e6")
    ax_main.spines["left"].set_linewidth(1.5)
    ax_main.spines["bottom"].set_color("#dee2e6")
    ax_main.spines["bottom"].set_linewidth(1.5)

    # Легенда
    ax_main.legend(
        loc="upper left",
        fontsize=10,
        frameon=True,
        fancybox=True,
        shadow=True,
        framealpha=0.98,
        edgecolor="#dee2e6",
    )

    # Формат дат на оси X
    fig.autofmt_xdate(rotation=25, ha="right")

    # ========== МЕТРИКИ ==========
    ax_metrics = fig.add_subplot(gs[2])
    ax_metrics.axis("off")
    ax_metrics.set_xlim(0, 1)
    ax_metrics.set_ylim(0, 1)

    # Данные метрик
    metric_cards = [
        {
            "symbol": "₽",
            "label": "Выручка",
            "value": f"{metrics['revenue']:,.0f}",
            "unit": "₽",
            "change": metrics.get("revenue_change_pct"),
            "color": "#0056b3",
            "x": 0.02,
        },
        {
            "symbol": "#",
            "label": "Заказы",
            "value": f"{metrics['orders']:,}",
            "unit": "шт",
            "change": metrics.get("orders_change_pct"),
            "color": "#28a745",
            "x": 0.21,
        },
        {
            "symbol": "Ø",
            "label": "Средний чек",
            "value": f"{metrics['avg_check']:,.0f}",
            "unit": "₽",
            "change": metrics.get("avg_check_change_pct"),
            "color": "#17a2b8",
            "x": 0.40,
        },
        {
            "symbol": "%",
            "label": "Комиссия",
            "value": f"{metrics['commission']:,.0f}",
            "unit": "₽",
            "change": None,
            "color": "#ffc107",
            "x": 0.59,
        },
        {
            "symbol": "✓",
            "label": "Прибыль",
            "value": f"{metrics['profit']:,.0f}",
            "unit": "₽",
            "change": None,
            "color": "#28a745",
            "x": 0.78,
        },
    ]

    # Рисуем карточки метрик
    for card in metric_cards:
        # Фон карточки с тенью
        shadow = FancyBboxPatch(
            (card["x"] + 0.003, 0.12),
            0.17,
            0.75,
            boxstyle="round,pad=0.02",
            facecolor="#adb5bd",
            edgecolor="none",
            alpha=0.15,
            transform=ax_metrics.transAxes,
            zorder=1,
        )
        ax_metrics.add_patch(shadow)

        rect = FancyBboxPatch(
            (card["x"], 0.15),
            0.17,
            0.75,
            boxstyle="round,pad=0.02",
            facecolor="white",
            edgecolor="#e9ecef",
            linewidth=2,
            transform=ax_metrics.transAxes,
            zorder=2,
        )
        ax_metrics.add_patch(rect)

        # Цветная полоска сверху
        top_bar = Rectangle(
            (card["x"] + 0.01, 0.82),
            0.15,
            0.05,
            facecolor=card["color"],
            edgecolor="none",
            transform=ax_metrics.transAxes,
            zorder=3,
            clip_on=False,
        )
        ax_metrics.add_patch(top_bar)

        # Символ метрики
        ax_metrics.text(
            card["x"] + 0.085,
            0.72,
            card["symbol"],
            fontsize=28,
            fontweight="bold",
            color=card["color"],
            ha="center",
            va="center",
            transform=ax_metrics.transAxes,
            zorder=4,
            alpha=0.9,
        )

        # Название метрики
        ax_metrics.text(
            card["x"] + 0.085,
            0.52,
            card["label"],
            fontsize=9,
            color="#6c757d",
            ha="center",
            va="center",
            transform=ax_metrics.transAxes,
            zorder=4,
            fontweight="500",
        )

        # Значение
        ax_metrics.text(
            card["x"] + 0.085,
            0.35,
            card["value"],
            fontsize=13,
            fontweight="bold",
            color="#212529",
            ha="center",
            va="center",
            transform=ax_metrics.transAxes,
            zorder=4,
        )

        # Единица измерения
        ax_metrics.text(
            card["x"] + 0.085,
            0.26,
            card["unit"],
            fontsize=8,
            color="#adb5bd",
            ha="center",
            va="center",
            transform=ax_metrics.transAxes,
            zorder=4,
        )

        # Изменение (если есть)
        if card["change"] is not None:
            change_color = "#28a745" if card["change"] >= 0 else "#dc3545"
            change_symbol = "▲" if card["change"] >= 0 else "▼"
            change_text = f"{change_symbol} {abs(card['change']):.1f}%"

            # Фон для изменения
            change_bg = FancyBboxPatch(
                (card["x"] + 0.03, 0.17),
                0.11,
                0.06,
                boxstyle="round,pad=0.005",
                facecolor=change_color,
                edgecolor="none",
                alpha=0.15,
                transform=ax_metrics.transAxes,
                zorder=3,
            )
            ax_metrics.add_patch(change_bg)

            ax_metrics.text(
                card["x"] + 0.085,
                0.20,
                change_text,
                fontsize=8,
                color=change_color,
                fontweight="700",
                ha="center",
                va="center",
                transform=ax_metrics.transAxes,
                zorder=4,
            )

    # Сохранение в буфер
    plt.subplots_adjust(left=0.05, right=0.98, top=0.96, bottom=0.08)
    buf = io.BytesIO()
    fig.savefig(
        buf,
        format="png",
        bbox_inches="tight",
        facecolor="#f5f7fa",
        dpi=150,
        pad_inches=0.3,
    )
    plt.close(fig)
    buf.seek(0)

    return buf.read()


def _generate_tips(metrics_curr, metrics_prev, top5_curr, prev_top5):
    tips = []
    if (
        metrics_prev
        and metrics_curr["revenue"] is not None
        and metrics_prev.get("revenue") is not None
    ):
        pct = _pct_change(metrics_curr["revenue"], metrics_prev["revenue"])
        if pct is not None and pct < -15:
            tips.append(f"Продажи упали на {abs(pct)}% — проверь активность рекламы.")
    if top5_curr:
        if top5_curr[0]["revenue_pct"] > 40:
            tips.append(
                f"Основная выручка от {top5_curr[0]['title']} — возможна зависимость."
            )
    if metrics_prev and metrics_prev.get("orders") is not None:
        if metrics_curr["avg_check"] < metrics_prev.get(
            "avg_check", 0
        ) and metrics_curr["orders"] > metrics_prev.get("orders", 0):
            tips.append("Скидки/акции снизили средний чек.")
    prev_skus = {p["sku"] for p in (prev_top5 or [])}
    for p in top5_curr:
        if p["sku"] not in prev_skus:
            tips.append(f"Новый лидер: {p['title']}.")
            break
    if not tips:
        tips.append("Показатели стабильны — продолжайте в том же духе.")
    return tips


def analyze_file(content: bytes, filename: str, period: str):
    df = _read_table(content, filename)
    df = _ensure_columns(df)
    start, end = _period_bounds(df, period)
    mask = (df["date"].dt.normalize() >= start) & (df["date"].dt.normalize() <= end)
    df_curr = df.loc[mask].copy()
    if df_curr.empty:
        raise ValueError("No data in the requested period")

    delta = end - start
    prev_start = start - delta - pd.Timedelta(days=1) + pd.Timedelta(days=0)
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

    tips = _generate_tips(metrics_curr, metrics_prev, top5_curr, top5_prev)

    chart = _generate_dashboard_chart(df_curr, metrics_curr)

    return {
        "metrics": metrics_curr,
        "top5": top5_curr,
        "tips": tips,
        "chart_png": chart,
        "meta": {
            "source": "CSV",
            "mode": "manual",
            "period": period,
            "rows_processed": len(df),
        },
    }
