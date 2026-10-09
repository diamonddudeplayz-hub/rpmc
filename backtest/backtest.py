"""RPMC 2027 backtest: portfolio Sharpe in rising- vs falling-rate periods.

    python backtest.py fetch  [--years 3]     # needs `pip install yfinance`; run where Yahoo/FRED are reachable
    python backtest.py run    [--years 3]     # reads data/prices.csv + data/rates.csv
    python backtest.py selftest               # synthetic data, checks the pipeline only (NOT real results)

Method (kept simple so it can be defended in the presentation):
  * Daily returns, constant target weights (rebalanced daily), no shorts, no costs.
  * Prices converted to CAD (the competition account is CAD) when data/prices.csv has USDCAD.
  * Rf = 3M T-bill yield (FRED DGS3MO), the "zero risk" asset in the RPMC Sharpe definition.
  * Sharpe = mean(daily excess return) / std(daily return) * sqrt(252).
  * Regimes: history is cut into non-overlapping blocks of N trading days (default 63, ~1 quarter).
    A block is RISING / FALLING / FLAT by the change in the chosen yield over the block. This is an
    ex-post label (describes what happened), it is not a forecast. Daily returns of all blocks with the
    same label are pooled and a Sharpe is computed on the pool.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
DATA = HERE / "data"
PORTFOLIO_FILE = HERE / "portfolio.json"
MAX_WEIGHT = 0.25  # official RPMC rule (PDF): each security/ETF <= 25% of portfolio
CAD_LISTED_SUFFIXES = (".TO", ".K")  # listed in CAD; everything else assumed USD

BENCHMARK = {"SPY": 0.35, "XIC.TO": 0.15, "IEMG": 0.20, "XBB.TO": 0.20, "GLD": 0.10}
# PDF lists IEMG as "IEMG.K" (RPM's ticker); it is the USD-listed iShares Core MSCI EM ETF.


def load_portfolio(name):
    return json.loads(PORTFOLIO_FILE.read_text())[name]


def fetch(years):
    try:
        import yfinance as yf
    except ImportError:
        sys.exit("pip install yfinance first (and run somewhere that can reach Yahoo/FRED)")
    names = set(BENCHMARK)
    for p in json.loads(PORTFOLIO_FILE.read_text()).values():
        names |= set(p)
    start = (pd.Timestamp.today() - pd.DateOffset(years=years, months=3)).date()
    px = yf.download(sorted(names) + ["USDCAD=X"], start=str(start), auto_adjust=True, progress=False)["Close"]
    px = px.rename(columns={"USDCAD=X": "USDCAD"})
    DATA.mkdir(exist_ok=True)
    px.to_csv(DATA / "prices.csv")
    series = {s: pd.read_csv(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}",
                             index_col=0, parse_dates=True, na_values=".").iloc[:, 0]
              for s in ("DGS3MO", "DGS2", "DGS10")}
    pd.DataFrame(series).to_csv(DATA / "rates.csv")
    print(f"wrote {DATA/'prices.csv'} and {DATA/'rates.csv'}")


def load_data(years):
    px = pd.read_csv(DATA / "prices.csv", index_col=0, parse_dates=True).sort_index()
    rates = pd.read_csv(DATA / "rates.csv", index_col=0, parse_dates=True).sort_index()
    return px, rates, years


def to_cad(px):
    if "USDCAD" not in px:
        print("WARNING: no USDCAD column, returns are in listing currency (no FX effect).")
        return px.drop(columns=["USDCAD"], errors="ignore")
    fx = px["USDCAD"]
    out = px.drop(columns=["USDCAD"]).copy()
    for t in out:
        if not t.endswith(CAD_LISTED_SUFFIXES):
            out[t] = out[t] * fx
    return out


def sharpe(excess, total):
    return float(excess.mean() / total.std() * np.sqrt(252)) if len(total) > 2 and total.std() > 0 else float("nan")


def max_drawdown(r):
    wealth = (1 + r).cumprod()
    return float((wealth / wealth.cummax() - 1).min())


def stats(r, rf):
    ex = r - rf.reindex(r.index)
    return {"days": len(r), "ann_ret": r.mean() * 252, "ann_vol": r.std() * np.sqrt(252),
            "sharpe": sharpe(ex, r)}


def label_blocks(rate, idx, block, thresh):
    rate = rate.reindex(idx).ffill().bfill()
    lab = pd.Series("", index=idx)
    for s in range(0, len(idx) - block + 1, block):
        chg = rate.iloc[s + block - 1] - rate.iloc[max(s - 1, 0)]
        lab.iloc[s:s + block] = "RISING" if chg > thresh else "FALLING" if chg < -thresh else "FLAT"
    return lab


def port_returns(rets, weights):
    w = pd.Series(weights).reindex(rets.columns).fillna(0.0)
    missing = set(weights) - set(rets.columns)
    if missing:
        sys.exit(f"no price data for: {sorted(missing)}")
    return rets @ w / w.sum()


def report(px, rates, args, portfolios):
    px = to_cad(px).dropna()
    rets = px.pct_change().dropna()
    rf = (rates["DGS3MO"].reindex(rets.index).ffill().bfill() / 100) / 252
    cutoff = rets.index[-1] - pd.DateOffset(years=args.years)
    rets, rf = rets[rets.index > cutoff], rf[rf.index > cutoff]
    ratesig = rates[args.rate]
    labels = label_blocks(ratesig, rets.index, args.block, args.thresh)

    print(f"\nData: {rets.index[0].date()} to {rets.index[-1].date()} ({len(rets)} trading days), CAD terms")
    print(f"Regime signal: {args.rate}, {args.block}-day blocks, threshold +/-{args.thresh:.2f}pp")
    print("Blocks by label:", {k: int(v // args.block) for k, v in labels.value_counts().items() if k})

    series = {n: port_returns(rets, w) for n, w in portfolios.items()}
    series["RPMC Benchmark"] = port_returns(rets, BENCHMARK)
    series["SPY"] = rets["SPY"]

    for name, w in portfolios.items():
        over = {t: x for t, x in w.items() if x > MAX_WEIGHT}
        tot = sum(w.values())
        print(f"[{name}] weights sum to {tot:.2f}" + (f"  OVER {MAX_WEIGHT:.0%} CAP: {over}" if over else ""))

    rows = []
    for name, r in series.items():
        for reg in ("ALL", "RISING", "FALLING", "FLAT"):
            sel = r if reg == "ALL" else r[labels.reindex(r.index) == reg]
            if len(sel) > 20:
                rows.append({"series": name, "regime": reg, **stats(sel, rf)})
        rows.append({"series": name, "regime": "MaxDD", "days": np.nan, "ann_ret": max_drawdown(r),
                     "ann_vol": np.nan, "sharpe": np.nan})
    out = pd.DataFrame(rows)
    fmt = out.copy()
    for c in ("ann_ret", "ann_vol"):
        fmt[c] = fmt[c].map(lambda v: "" if pd.isna(v) else f"{v:.1%}")
    fmt["sharpe"] = fmt["sharpe"].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    fmt["days"] = fmt["days"].map(lambda v: "" if pd.isna(v) else int(v))
    print("\n(MaxDD row: value is in the ann_ret column)\n" + fmt.to_string(index=False))

    names = list(portfolios)[0]
    cols = [t for t in portfolios[names]]
    corr = rets[cols].corr()
    avg = (corr.values.sum() - len(cols)) / (len(cols) * (len(cols) - 1))
    print(f"\nAvg pairwise correlation of holdings: {avg:.2f}\n{corr.round(2).to_string()}")
    return out


def selftest():
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2023-01-02", periods=900)
    names = set(BENCHMARK)
    for p in json.loads(PORTFOLIO_FILE.read_text()).values():
        names |= set(p)
    px = pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(3e-4, 0.01, len(idx))) for t in sorted(names)}, index=idx)
    px["USDCAD"] = 1.35 * np.cumprod(1 + rng.normal(0, 0.003, len(idx)))
    rates = pd.DataFrame({"DGS3MO": 4 + np.cumsum(rng.normal(0, 0.03, len(idx))),
                          "DGS2": 4 + np.cumsum(rng.normal(0, 0.04, len(idx))),
                          "DGS10": 4 + np.cumsum(rng.normal(0, 0.05, len(idx)))}, index=idx)
    print("*** SYNTHETIC RANDOM DATA: pipeline check only, numbers mean nothing ***")
    args = argparse.Namespace(years=3, rate="DGS10", block=63, thresh=0.25)
    report(px, rates, args, {"current_8": load_portfolio("current_8")})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "run", "selftest"])
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--rate", default="DGS10", choices=["DGS3MO", "DGS2", "DGS10"],
                    help="yield used to label rising/falling blocks")
    ap.add_argument("--block", type=int, default=63, help="trading days per regime block")
    ap.add_argument("--thresh", type=float, default=0.25, help="pp change over a block to count as rising/falling")
    ap.add_argument("--portfolios", nargs="*", help="names from portfolio.json (default: all)")
    args = ap.parse_args()
    if args.cmd == "fetch":
        fetch(args.years)
    elif args.cmd == "selftest":
        selftest()
    else:
        px, rates, _ = load_data(args.years)
        allp = json.loads(PORTFOLIO_FILE.read_text())
        report(px, rates, args, {n: allp[n] for n in (args.portfolios or allp)})


if __name__ == "__main__":
    main()
