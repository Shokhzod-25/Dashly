import io
import pandas as pd
import matplotlib

matplotlib.use("Agg")
from matplotlib import gridspec
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np
import asyncio
from concurrent.futures import ThreadPoolExecutor


async def generate_dashboard_chart_async(df_period: pd.DataFrame, metrics: dict):
    def _blocking_generate():
        return _generate_dashboard_chart(df_period, metrics)

    with ThreadPoolExecutor() as executor:
        return await asyncio.get_event_loop().run_in_executor(
            executor, _blocking_generate
        )


def _generate_dashboard_chart(df_period: pd.DataFrame, metrics: dict):
    if df_period.empty:
        df_period = pd.DataFrame(
            {"date": [pd.Timestamp.now()], "revenue": [0], "qty": [0]}
        )
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

    fig = plt.figure(figsize=(14, 8), dpi=150)
    fig.patch.set_facecolor("#f5f7fa")

    gs = gridspec.GridSpec(3, 1, height_ratios=[0.4, 2.2, 1.2], hspace=0.35)

    ax_header = fig.add_subplot(gs[0])
    ax_header.axis("off")
    ax_header.set_xlim(0, 1)
    ax_header.set_ylim(0, 1)

    ax_header.text(
        0.02,
        0.5,
        "DASHLY",
        fontsize=22,
        fontweight="bold",
        color="#0056b3",
        va="center",
    )

    period_text = f"За период: {len(daily)} дней"
    ax_header.text(
        0.15,
        0.5,
        f"Аналитика продаж • {period_text}",
        fontsize=11,
        color="#6c757d",
        va="center",
        style="italic",
    )

    ax_header.text(
        0.98,
        0.5,
        f"Обновлено: {pd.Timestamp.now().strftime('%d.%m.%Y %H:%M')}",
        fontsize=9,
        color="#adb5bd",
        va="center",
        ha="right",
    )

    ax_main = fig.add_subplot(gs[1])
    ax_main.set_facecolor("#ffffff")

    ax_main.fill_between(x, y_revenue, color="#0056b3", alpha=0.12)

    ax_main.plot(
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

    ax_main.grid(axis="y", linestyle="-", alpha=0.15, color="#dee2e6", linewidth=1)
    ax_main.grid(axis="x", linestyle="-", alpha=0.08, color="#dee2e6", linewidth=0.5)
    ax_main.spines["top"].set_visible(False)
    ax_main.spines["right"].set_visible(False)
    ax_main.spines["left"].set_color("#dee2e6")
    ax_main.spines["left"].set_linewidth(1.5)
    ax_main.spines["bottom"].set_color("#dee2e6")
    ax_main.spines["bottom"].set_linewidth(1.5)

    ax_main.legend(
        loc="upper left",
        fontsize=10,
        frameon=True,
        fancybox=True,
        shadow=True,
        framealpha=0.98,
        edgecolor="#dee2e6",
    )

    fig.autofmt_xdate(rotation=25, ha="right")

    # Метрики
    ax_metrics = fig.add_subplot(gs[2])
    ax_metrics.axis("off")
    ax_metrics.set_xlim(0, 1)
    ax_metrics.set_ylim(0, 1)

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

    for card in metric_cards:
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

        if card["change"] is not None:
            change_color = "#28a745" if card["change"] >= 0 else "#dc3545"
            change_symbol = "▲" if card["change"] >= 0 else "▼"
            change_text = f"{change_symbol} {abs(card['change']):.1f}%"

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
