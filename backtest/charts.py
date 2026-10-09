"""Four quick charts for the group chat. Run from backtest/ after `python backtest.py build`:

    python charts.py            # writes PNGs to ../charts/

Book = portfolio.json["final_no_adbe"]. All numbers are backtests in CAD terms, picked with hindsight.
"""
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analysis as an
import backtest as bt

BOOK = "final_no_adbe"
OUT = bt.HERE.parent / "charts"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#8a8985"  # palette slots 1, 2 + neutral reference

plt.rcParams.update({
    "font.size": 13, "axes.titlesize": 17, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "legend.frameon": False, "savefig.facecolor": SURFACE,
})


def finish(fig, ax, title, sub, name):
    sub = textwrap.fill(sub, 64)  # keep the subtitle well inside the figure edge
    ax.set_title(title, pad=16 + 17 * (sub.count("\n") + 1))
    ax.text(0, 1.02, sub, transform=ax.transAxes, color=INK2, fontsize=11.5, va="bottom", linespacing=1.3)
    fig.tight_layout()
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / name, dpi=170)
    plt.close(fig)


def main():
    book = bt.load_portfolio(BOOK)
    rets, rf = an.prepare(5)
    mine = bt.port_returns(rets, book)
    bench = bt.port_returns(rets, bt.BENCHMARK)
    spy = rets["SPY"]

    # 1. growth of CAD $1
    fig, ax = plt.subplots(figsize=(9, 5.4))
    for s, c, lab, lw in ((mine, BLUE, "Our book", 2.2), (bench, ORANGE, "RPMC benchmark", 2.2), (spy, GREY, "SPY", 1.6)):
        g = (1 + s).cumprod()
        ax.plot(g.index, g.values, color=c, lw=lw, label=lab)
        ax.annotate(f"${g.iloc[-1]:.2f}", (g.index[-1], g.iloc[-1]), xytext=(6, 0), textcoords="offset points", va="center", color=INK, fontsize=12)
    ax.set_xlim(right=rets.index[-1] + pd.Timedelta(days=90))
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:.1f}")
    ax.legend(loc="upper left")
    finish(fig, ax, "CAD $1 over 5 years", "Backtest, CAD terms, daily rebalanced, holdings picked with hindsight", "1_growth_of_1.png")

    # 2. rolling 105-day Sharpe
    def roll(r):
        ex = r - rf.reindex(r.index)
        return (ex.rolling(105).mean() / r.rolling(105).std() * np.sqrt(252)).dropna()

    rm, rb = roll(mine), roll(bench)
    fig, ax = plt.subplots(figsize=(9, 5.4))
    ax.plot(rm.index, rm.values, color=BLUE, lw=2, label="Our book")
    ax.plot(rb.index, rb.values, color=ORANGE, lw=2, label="RPMC benchmark")
    ax.axhline(0, color=INK2, lw=1)
    j = rm.align(rb, join="inner")
    ax.legend(loc="upper left")
    ax.set_ylabel("Sharpe of the trailing 105 days")
    finish(fig, ax, "What a competition-length window looks like",
           f"Every 105-day stretch since 2022: our book beat the benchmark in {np.mean(j[0] > j[1]):.0%} of them and lost money in {np.mean(rm < 0):.0%}", "2_rolling_105d_sharpe.png")

    # 3. weight vs share of risk
    w = pd.Series(book)
    cov = rets[w.index].cov() * 252
    risk = (w * (cov @ w) / (w @ cov @ w)).reindex(w.sort_values().index)
    wt = w.reindex(risk.index)
    fig, ax = plt.subplots(figsize=(9, 5.4))
    y = np.arange(len(risk))
    ax.barh(y + 0.19, wt.values * 100, height=0.34, color=BLUE, label="Weight in the book")
    ax.barh(y - 0.19, risk.values * 100, height=0.34, color=ORANGE, label="Share of the book's risk")
    for yi, a, b in zip(y, wt.values, risk.values):
        ax.text(max(a, 0) * 100 + 0.6, yi + 0.19, f"{a:.0%}", va="center", fontsize=11, color=INK)
        ax.text(max(b, 0) * 100 + 0.6, yi - 0.19, f"{b:.0%}", va="center", fontsize=11, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels(risk.index)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("% of portfolio")
    ax.legend(loc="upper right")
    finish(fig, ax, "Weight vs where the risk actually sits", "Share of portfolio variance, 5-year daily data. GLD, XLV, TBF are the diversifiers", "3_weight_vs_risk.png")

    # 4. Hormuz headline days
    esc = [an.ESCALATION, an.DEESCALATION]
    px_days = lambda ds: [rets.index[rets.index.searchsorted(pd.Timestamp(d))] for d in ds]
    rets2 = rets.assign(BOOK=mine)
    cols = ["LNG", "TBF", "GLD", "BOOK"]
    e = rets2.loc[px_days(an.ESCALATION), cols].mean() * 100
    d = rets2.loc[px_days(an.DEESCALATION), cols].mean() * 100
    fig, ax = plt.subplots(figsize=(9, 5.4))
    x = np.arange(len(cols))
    ax.bar(x - 0.19, e.values, width=0.34, color=ORANGE, label=f"Escalation days (n={len(an.ESCALATION)})")
    ax.bar(x + 0.19, d.values, width=0.34, color=BLUE, label=f"De-escalation days (n={len(an.DEESCALATION)})")
    for xi, a, b in zip(x, e.values, d.values):
        ax.text(xi - 0.19, a + (0.12 if a >= 0 else -0.12), f"{a:+.1f}%", ha="center", va="bottom" if a >= 0 else "top", fontsize=11, color=INK)
        ax.text(xi + 0.19, b + (0.12 if b >= 0 else -0.12), f"{b:+.1f}%", ha="center", va="bottom" if b >= 0 else "top", fontsize=11, color=INK)
    ax.axhline(0, color=INK2, lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels(["LNG", "TBF", "GLD", "Our book"])
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Average same-day return")
    ax.set_ylim(min(e.min(), d.min()) - 1, max(e.max(), d.max()) + 1)
    ax.legend(loc="upper right")
    finish(fig, ax, "Hormuz headline days: LNG and GLD offset", "LNG and TBF win on escalation, GLD on de-escalation, so the book ends up roughly flat. Nine days, treat as a sketch", "4_hormuz_headline_days.png")
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
