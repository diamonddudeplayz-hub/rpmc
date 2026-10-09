"""Follow-up checks on the current 8-position book. Run from backtest/ after `python backtest.py build`:

    python analysis.py

Uses the same data and income handling as `backtest.py run --income` (CAD terms, SHV = T-bill carry).
"""
import json

import numpy as np
import pandas as pd

import backtest as bt

# Hormuz headline days taken from the hormuzstraitmonitor.com timeline you pasted (not verified independently).
# If the date is not a trading day in the data, the next trading day is used.
ESCALATION = ["2026-03-02", "2026-07-07", "2026-07-23", "2026-09-24"]
DEESCALATION = ["2026-04-08", "2026-04-17", "2026-06-15", "2026-07-27", "2026-08-25"]
SHOW = ["LNG", "TBF", "GLD", "NVDA", "AVGO", "XLV", "ITRI", "SPY"]


def prepare(years):
    px, rates, _ = bt.load_data(years)
    rets = bt.to_cad(px).dropna().pct_change().dropna()
    rf = (rates["DGS3MO"].reindex(rets.index).ffill().bfill() / 100) / 252
    rets = bt.add_income(rets, rf, json.loads((bt.HERE / "income_assumptions.json").read_text()))
    cutoff = rets.index[-1] - pd.DateOffset(years=years)
    return rets[rets.index > cutoff], rf[rf.index > cutoff]


def sharpe_of(rets, rf, w):
    r = bt.port_returns(rets, w)
    return bt.stats(r, rf)["sharpe"], r


def main():
    book = bt.load_portfolio("current_8")
    for years in (5, 2):
        rets, rf = prepare(years)
        print(f"\n################ {years}Y  ({rets.index[0].date()} to {rets.index[-1].date()})")

        # 1. Where the risk actually sits
        w = pd.Series(book)
        cov = rets[w.index].cov() * 252
        contrib = w * (cov @ w) / (w @ cov @ w)
        vol = np.sqrt(np.diag(cov))
        print("\nRisk contribution (share of portfolio variance) vs weight, and standalone vol:")
        for t in w.sort_values(ascending=False).index:
            print(f"  {t:5s} weight {w[t]:4.0%}   risk share {contrib[t]:5.0%}   own vol {vol[list(w.index).index(t)]:5.1%}")

        # 2. Does SHV help Sharpe? (it should not: mixing in the risk-free asset leaves Sharpe unchanged)
        s_all, _ = sharpe_of(rets, rf, book)
        s_noshv, _ = sharpe_of(rets, rf, {t: x for t, x in book.items() if t != "SHV"})
        print(f"\nSharpe with SHV 15%: {s_all:.2f}   without SHV (rest scaled up to 100%): {s_noshv:.2f}")

        # 3. Inverse-vol sizing of the 4 single names vs what we hold (sleeve = 50%)
        names = ["ITRI", "LNG", "AVGO", "NVDA"]
        iv = 1 / pd.Series(vol, index=w.index)[names]
        iv = iv / iv.sum() * sum(book[n] for n in names)
        print("\nEquity sleeve, held weight vs inverse-vol weight:")
        print("  " + "   ".join(f"{n} {book[n]:.0%}->{iv[n]:.1%}" for n in names))

        # 4. The NVDA / AVGO swap: keep one, move its weight into something less correlated
        print("\nSwap options (Sharpe, income-adjusted):")
        print(f"  current book                    {s_all:.2f}")
        for drop in ("AVGO", "NVDA"):
            for new in ("XLV", "XIC.TO", "IEMG"):
                v = dict(book)
                v[new] = v.get(new, 0) + v.pop(drop)
                if max(v.values()) > bt.MAX_WEIGHT:
                    continue
                s, _ = sharpe_of(rets, rf, v)
                print(f"  drop {drop:4s} -> {new:7s} ({v[new]:.0%})      {s:.2f}")
        v = dict(book)
        v["AVGO"], v["NVDA"] = 0.06, 0.06
        v["XLV"] += 0.10
        s, _ = sharpe_of(rets, rf, v)
        print(f"  halve both, +10% XLV            {s:.2f}")

        # 5. Who drove return over this window (weight x standalone annual return)
        ann = rets[w.index].mean() * 252
        print("\nContribution to annual return (weight x own return):")
        print("  " + "   ".join(f"{t} {w[t] * ann[t]:+.1%}" for t in w.sort_values(ascending=False).index))

    # 6. Hormuz event study (5y data covers the whole war)
    rets, rf = prepare(5)
    port = bt.port_returns(rets, book)
    rets = rets.assign(PORT=port)

    def day(d):
        i = rets.index.searchsorted(pd.Timestamp(d))
        return rets.index[i]

    print("\n################ Hormuz event study: same-day return (%), CAD")
    for label, dates in (("ESCALATION days", ESCALATION), ("DE-ESCALATION days", DEESCALATION)):
        rows = pd.DataFrame({day(d).date(): rets.loc[day(d), SHOW + ["PORT"]] * 100 for d in dates}).T
        print(f"\n{label}")
        print(rows.round(1).to_string())
        print("average".ljust(10) + "  ".join(f"{c}:{rows[c].mean():+.1f}" for c in rows.columns))


if __name__ == "__main__":
    main()
