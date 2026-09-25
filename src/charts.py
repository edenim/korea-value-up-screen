"""Static charts for the README and the initiation note (matplotlib, PNG)."""

import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from config import CHART_DIR

# Reference palette (dataviz skill, light mode). Scatter uses at most 3 series.
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
NEUTRAL_DOT = "#b5b4ad"
SERIES_1 = "#2a78d6"  # candidates with a Value-Up plan
SERIES_2 = "#eb6834"  # candidates without a Value-Up plan

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT_SECONDARY,
    "xtick.color": TEXT_SECONDARY, "ytick.color": TEXT_SECONDARY,
    "text.color": TEXT_PRIMARY, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
})


def short_name(name_eng, fallback):
    """'Hyundai Motor Company' -> 'Hyundai Motor'. Falls back to the code if no English name."""
    if not isinstance(name_eng, str) or not name_eng.strip():
        return fallback
    name = re.sub(r"(?i)\b(co\.?,?\s*ltd\.?|corporation|corp\.?|company|inc\.?|holdings?)\b", "", name_eng)
    return re.sub(r"\s+", " ", name).strip(" ,.")


def pb_vs_roe(df, cands, model):
    fig, ax = plt.subplots(figsize=(8, 5.2))
    others = df[~df.index.isin(cands.index)]
    ax.scatter(others["roe_w"] * 100, np.exp(others["sector_adj_log_pb"]), s=18,
               color=NEUTRAL_DOT, edgecolor=SURFACE, linewidth=0.8, label="Universe", zorder=2)

    for flag, color, label in [(True, SERIES_1, "Candidate, Value-Up plan filed"),
                               (False, SERIES_2, "Candidate, no Value-Up plan")]:
        sub = cands[cands["valueup_plan"] == flag]
        ax.scatter(sub["roe_w"] * 100, np.exp(sub["sector_adj_log_pb"]), s=40, color=color,
                   edgecolor=SURFACE, linewidth=1.5, label=label, zorder=3)

    x = np.linspace(df["roe_w"].min(), df["roe_w"].max(), 100)
    y = np.exp(model.params["Intercept"] + model.params["roe_w"] * x)
    ax.plot(x * 100, y, color=TEXT_SECONDARY, linewidth=2, label="Model (sector-adjusted fit)", zorder=1)

    label_candidates(ax, cands.head(8))

    ax.set_yscale("log")
    ax.set_xlabel("ROE, FY2025 (%, winsorized 1/99)")
    ax.set_ylabel("Sector-adjusted P/B (x, log scale)")
    ax.set_title("KOSPI non-financials: P/B vs ROE after removing sector effects",
                 loc="left", fontsize=11, color=TEXT_PRIMARY)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.text(0.01, 0.01, "Below the line = trading below the P/B its ROE and sector justify. "
             "Top 8 candidates labeled. Source: DART, FinanceDataReader.",
             fontsize=7, color=TEXT_SECONDARY)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(CHART_DIR / "pb_vs_roe.png", dpi=200)
    plt.close(fig)


def label_candidates(ax, cands, label_x=25.0, min_gap=0.08):
    """Label points on a log-y axis without overlaps.

    Labels are stacked in one column at x=label_x, sorted by height, so leader lines
    never cross. Points already right of the column get a label just beside them.
    min_gap is the minimum vertical spacing between labels, in log10 units.
    """
    pts = sorted(((r["roe_w"] * 100, r["sector_adj_log_pb"] / np.log(10),
                   short_name(r.get("name_eng"), r["code"])) for _, r in cands.iterrows()),
                 key=lambda t: t[1])
    placed = []
    for x, y, text in pts:
        if x >= label_x - 1:
            tx, ty = x + 1.2, y
        else:
            ty = y if not placed else max(y, placed[-1] + min_gap)
            placed.append(ty)
            tx = label_x
        ax.annotate(text, (x, 10 ** y), xytext=(tx, 10 ** ty), textcoords="data",
                    fontsize=7.5, color=TEXT_PRIMARY, va="center",
                    arrowprops=dict(arrowstyle="-", color=TEXT_SECONDARY, linewidth=0.6,
                                    shrinkA=0, shrinkB=3))


def residual_by_sector(df):
    order = df.groupby("sector")["residual_pooled"].median().sort_values().index.tolist()
    fig, ax = plt.subplots(figsize=(8, 0.38 * len(order) + 1.2))
    rng = np.random.default_rng(0)  # fixed jitter so the chart is reproducible

    for i, sector in enumerate(order):
        vals = df.loc[df["sector"] == sector, "residual_pooled"]
        ax.scatter(np.exp(vals), i + rng.uniform(-0.15, 0.15, len(vals)), s=12,
                   color=NEUTRAL_DOT, edgecolor=SURFACE, linewidth=0.6, zorder=2)
        med = np.exp(vals.median())
        ax.scatter([med], [i], s=60, marker="|", color=SERIES_1, linewidth=2.5, zorder=3)
        ax.text(1.02, i, f"n={len(vals)}", transform=ax.get_yaxis_transform(),
                va="center", fontsize=7.5, color=TEXT_SECONDARY)

    # Log scale on the ratio actual/model, so +100% and -50% sit equally far from zero
    ax.set_xscale("log")
    ax.axvline(1, color=TEXT_SECONDARY, linewidth=1)
    ticks = [0.25, 0.5, 1, 2, 4]
    ax.set_xticks(ticks)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v - 1:+.0%}"))
    ax.xaxis.set_minor_formatter(plt.NullFormatter())
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order)
    ax.invert_yaxis()  # most discounted sector on top
    ax.set_xlabel("Actual P/B vs ROE-only model P/B (dots = companies, bar = sector median)")
    ax.set_title("Which sectors trade below the P/B their ROE implies", loc="left", fontsize=11)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "residual_by_sector.png", dpi=200)
    plt.close(fig)


def event_study_car(mean_cum_ar, n, t_stat):
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    ax.plot(mean_cum_ar.index, mean_cum_ar.values * 100, color=SERIES_1, linewidth=2,
            marker="o", markersize=5, markeredgecolor=SURFACE, markeredgewidth=1.5)
    ax.axhline(0, color=TEXT_SECONDARY, linewidth=1)
    ax.axvline(0, color=GRID, linewidth=1, linestyle="--")
    last = mean_cum_ar.iloc[-1] * 100
    ax.annotate(f"{last:+.2f}%", (mean_cum_ar.index[-1], last), xytext=(6, 0),
                textcoords="offset points", va="center", fontsize=8.5)
    ax.set_xticks(list(mean_cum_ar.index))
    ax.set_xlabel("Trading days relative to first Value-Up plan disclosure (day 0)")
    ax.set_ylabel("Mean cumulative abnormal return (%)")
    ax.set_title(f"Market reaction to first Value-Up plan (N={n})", loc="left", fontsize=11)
    fig.text(0.01, 0.01, f"CAR[-1,+5] t-stat {t_stat:.2f}, not significant. Market model vs KOSPI, "
             "estimation window [-250, -30]. "
             "Source: DART, FinanceDataReader.", fontsize=7, color=TEXT_SECONDARY)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(CHART_DIR / "event_study_car.png", dpi=200)
    plt.close(fig)


# ---------------- Kyung Dong Navien note charts ----------------
# Categorical palette in fixed order (dataviz reference palette, light mode)
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]


def navien_revenue_by_region(years, series, n_actual, path):
    """Stacked bars of revenue by region. series: {region: [values per year]} in KRW bn."""
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    bottom = np.zeros(len(years))
    for color, (name, vals) in zip(CATEGORICAL, series.items()):
        vals = np.array(vals)
        ax.bar(years, vals, bottom=bottom, color=color, edgecolor=SURFACE, linewidth=1.5, width=0.7, label=name)
        bottom += vals
    for i, total in enumerate(bottom):
        ax.text(i, total + 20, f"{total:,.0f}", ha="center", fontsize=7.5, color=TEXT_SECONDARY)
    ax.axvline(n_actual - 0.5, color=TEXT_SECONDARY, linewidth=1, linestyle="--")
    ax.text(n_actual - 0.45, bottom.max() * 1.07, "Forecast", fontsize=7.5, color=TEXT_SECONDARY)
    ax.set_ylabel("Revenue (KRW bn)")
    ax.set_ylim(0, bottom.max() * 1.15)
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=7.5, ncol=5, loc="upper left", bbox_to_anchor=(0, -0.1))
    ax.set_title("Revenue by region: North America is 58% of sales", loc="left", fontsize=10.5)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def navien_capex_fcf(years, capex, fcf, n_actual, path):
    """Grouped bars: capex vs free cash flow (CFO - capex), KRW bn."""
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    x = np.arange(len(years))
    w = 0.38
    ax.bar(x - w / 2, capex, w, color=CATEGORICAL[1], edgecolor=SURFACE, linewidth=1.5, label="Capex")
    ax.bar(x + w / 2, fcf, w, color=CATEGORICAL[0], edgecolor=SURFACE, linewidth=1.5,
           label="Free cash flow (CFO - capex)")
    ax.axhline(0, color=TEXT_SECONDARY, linewidth=1)
    ax.axvline(n_actual - 0.5, color=TEXT_SECONDARY, linewidth=1, linestyle="--")
    for i, v in enumerate(fcf):
        ax.text(i + w / 2, v + (4 if v >= 0 else -12), f"{v:,.0f}", ha="center", fontsize=7, color=TEXT_SECONDARY)
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.set_ylabel("KRW bn")
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=7.5, ncol=2, loc="upper left", bbox_to_anchor=(0, -0.1))
    ax.set_title("The capex cycle is ending: free cash flow turns positive", loc="left", fontsize=10.5)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def navien_valuation_range(rows, price, target, path):
    """Football field. rows: [(label, low, high)]; a point estimate has low == high."""
    fig, ax = plt.subplots(figsize=(6.5, 2.6))
    for i, (lab, lo, hi) in enumerate(rows):
        if hi > lo:
            ax.barh(i, hi - lo, left=lo, height=0.5, color=CATEGORICAL[0], alpha=0.85)
            ax.text(hi + 1500, i, f"{lo:,.0f} to {hi:,.0f}", va="center", fontsize=7.5, color=TEXT_SECONDARY)
        else:
            ax.scatter([lo], [i], s=60, color=CATEGORICAL[0], edgecolor=SURFACE, linewidth=1.5, zorder=3)
            ax.text(lo + 1500, i, f"{lo:,.0f}", va="center", fontsize=7.5, color=TEXT_SECONDARY)
    ax.axvline(price, color=TEXT_SECONDARY, linewidth=1.2)
    ax.text(price, -0.85, f"Price {price:,.0f}", ha="right", fontsize=7.5, color=TEXT_SECONDARY)
    ax.axvline(target, color=CATEGORICAL[1], linewidth=1.5, linestyle="--")
    ax.text(target, -0.85, f" Target {target:,.0f}", ha="left", fontsize=7.5, color=CATEGORICAL[1])
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=8)
    ax.invert_yaxis()
    ax.set_ylim(len(rows) - 0.5, -1.1)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlabel("Value per share (KRW)")
    ax.grid(axis="y", visible=False)
    ax.set_title("Valuation range", loc="left", fontsize=10.5)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
