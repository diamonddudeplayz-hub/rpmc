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
DIVIDENDS = HERE / "dividends.csv"
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


XLSX_DIR = HERE.parent  # LSEG Workspace exports sit in the repo root
RATE_FILES = {"us 3m.xlsx": "DGS3MO", "us 2y.xlsx": "DGS2", "us10y.xlsx": "DGS10"}


def read_lseg(path):
    """LSEG 'Table Data' export: row0 = header, row1 = 'Close', data below, newest first."""
    df = pd.read_excel(path, header=None, skiprows=2)
    s = pd.Series(df[1].astype(float).values, index=pd.to_datetime(df[0]))
    return s[~s.index.duplicated()].sort_index()


# sheet-name keywords (sheet names are cut at 31 chars) -> ticker, for weekly 'Rolling Performance' exports
ROLLING_NAMES = [("TSX", "XIC.TO"), ("VANGUARD", "VOO"), ("MSCI EAFE", "EFA"), ("AAA CLO", "JAAA"), ("ELI LILLY", "LLY"),
                 ("WALMART", "WMT"), ("ROYAL BANK", "RY.TO"), ("S&P 500", "SPY"), ("UNIVERSE BOND", "XBB.TO"), ("MSCI EMERGING", "IEMG"),
                 ("HEALTH CARE SELECT", "XLV"), ("SHORT 20", "TBF"), ("CHENIERE", "LNG"), ("BROADCOM", "AVGO"), ("NVIDIA", "NVDA")]  # matched against the full fund name in cell A1


def read_rolling(f):
    """Weekly total-return % per week-ending date (LSEG Rolling Performance). Returns (sheet name, Series of decimals)."""
    title = str(pd.read_excel(f, header=None, nrows=1).iloc[0, 0])
    d = pd.read_excel(f, header=None, skiprows=7)[[1, 2]].dropna()
    return title, pd.Series(d[2].astype(float).values / 100, index=pd.to_datetime(d[1]))


def build():
    px, rt, tr, weekly = {}, {}, {}, {}
    for f in sorted(XLSX_DIR.glob("*.xlsx")):
        head = pd.read_excel(f, header=None, nrows=6)
        if str(head.iloc[4, 0]).strip() == "Rolling Performance":
            weekly[f.name] = read_rolling(f)
            continue
        ric = str(head.iloc[0, 1]).split(" ")[0]
        s = read_lseg(f)
        if str(head.iloc[1, 1]).strip() == "Total Return":  # cumulative % since start of export
            tr[ric] = 1 + s / 100
            continue
        if f.name in RATE_FILES:
            rt[RATE_FILES[f.name]] = s
        elif ric == "CAD=":
            px["USDCAD"] = s
        else:
            px[ric.split(".")[0] if ric.endswith((".O", ".K")) else ric] = s
    DATA.mkdir(exist_ok=True)
    # exact total return for tickers with a dividend table: index_t = index_(t-1) * (P_t + D_t) / P_(t-1) on ex-dates
    dv = DIVIDENDS.read_text() if DIVIDENDS.exists() else ""
    if dv:
        d = pd.read_csv(DIVIDENDS, parse_dates=["ex_date"])
        d["amt"] = d["amount_as_listed"] / d["divide_by"]
        for t, g in d.groupby("ticker"):
            p = px[t].dropna()
            cash = pd.Series(0.0, index=p.index)
            for _, r in g.iterrows():
                i = p.index.searchsorted(r["ex_date"])
                if 0 < i < len(p):
                    cash.iloc[i] += r["amt"]
            tr[t] = ((p + cash) / p.shift(1)).fillna(1.0).cumprod()
            print(f"  {t}: exact total return from {len(g)} dividends, income {float(cash.sum() / p.mean() / (len(p) / 252)):.2%} of avg price a year")
    for t, idx in tr.items():  # use the total-return index in place of the price series (rescaled so the last value = last price)
        last = float(px[t].dropna().iloc[-1]) if t in px else 1.0
        px[t] = idx * (last / float(idx.iloc[-1]))
    (DATA / "tr_tickers.json").write_text(json.dumps(sorted(tr)))
    wk_income = {}
    for name, (title, perf) in weekly.items():
        t = next((tk for kw, tk in ROLLING_NAMES if kw in title.upper()), None)
        if t is None or t not in px or t in tr:
            print(f"  skipped {name}: '{title}' (no matching ticker, or it already has exact total return)"); continue
        wk = px[t].dropna().reindex(perf.index, method="ffill").pct_change()
        inc = (perf - wk).dropna()
        wk_income[t] = inc
        print(f"  {t}: weekly total return file -> income {float(inc.mean() * 52):.2%} a year ({name})")
    pd.DataFrame(wk_income).to_csv(DATA / "weekly_income.csv")
    pd.DataFrame(px).to_csv(DATA / "prices.csv")
    pd.DataFrame(rt).to_csv(DATA / "rates.csv")
    print("built", sorted(px), sorted(rt))


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


def add_income(rets, rf, assumptions):
    """LSEG TRDPRC_1 is price-only. Income mode (non-empty `assumptions`) adds distributions, best source first:
    1) tickers in tr_tickers.json already carry total return (SHV export, NVDA/LNG/AVGO from dividends.csv);
    2) weekly total-return exports (weekly_income.csv): the weekly income is spread over that week's trading days;
    3) SHV without an export = T-bill carry; anything left = constant yield assumptions."""
    rets = rets.copy()
    income_mode = bool(assumptions)
    f = DATA / "tr_tickers.json"
    have_tr = set(json.loads(f.read_text())) if f.exists() else set()
    covered = set(have_tr)
    w = DATA / "weekly_income.csv"
    if income_mode and w.exists():
        inc = pd.read_csv(w, index_col=0, parse_dates=True)
        for t in inc.columns:
            if t not in rets or t in have_tr:
                continue
            ser = inc[t].dropna()
            prev = ser.index.to_series().shift(1)
            for end, v in ser.items():
                if pd.isna(prev[end]):
                    continue
                days = rets.index[(rets.index > prev[end]) & (rets.index <= end)]
                if len(days):
                    rets.loc[days, t] += v / len(days)
            covered.add(t)
    if "SHV" in rets and "SHV" not in have_tr:
        # price series has monthly ex-div drops (fake noise), so model SHV purely as T-bill carry
        rets["SHV"] = (rf * 252 - 0.0015).clip(lower=0) / 252
        covered.add("SHV")
    for t, y in assumptions.items():
        if t in rets and t not in covered:
            rets[t] += y / 252
    return rets


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
    income = json.loads((HERE / "income_assumptions.json").read_text()) if args.income else {}
    rets = add_income(rets, rf, income)
    print("Income handling: SHV accrues T-bill yield" + (f"; plus assumed yields {income}" if income else
          "; all other tickers PRICE-ONLY (distributions ignored)"))
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

    win = 105  # trading days, Oct 9 -> Mar 12
    print(f"\nRolling {win}-trading-day Sharpe (what a competition-length window looks like):")
    roll = {}
    for name, r in series.items():
        ex = r - rf.reindex(r.index)
        roll[name] = (ex.rolling(win).mean() / r.rolling(win).std() * np.sqrt(252)).dropna()
    for name, v in roll.items():
        q = v.quantile([.1, .5, .9])
        print(f"  {name:15s} p10 {q[.1]:6.2f}  median {q[.5]:6.2f}  p90 {q[.9]:6.2f}   share of windows with Sharpe<0: {(v<0).mean():.0%}")
    first = list(portfolios)[0]
    for name in list(portfolios) + ["SPY"]:
        j = roll[name].align(roll["RPMC Benchmark"], join="inner")
        print(f"  {name} beats RPMC Benchmark in {(j[0] > j[1]).mean():.0%} of windows")

    print("\nStandalone holdings (CAD, ann.):")
    allt = sorted({t for w in portfolios.values() for t in w} | set(BENCHMARK))
    for t in allt:
        st = stats(rets[t], rf)
        print(f"  {t:7s} ret {st['ann_ret']:6.1%}  vol {st['ann_vol']:6.1%}  Sharpe {st['sharpe']:5.2f}")

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
    args = argparse.Namespace(years=3, rate="DGS10", block=63, thresh=0.25, income=False)
    report(px, rates, args, {"current_8": load_portfolio("current_8")})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "build", "run", "selftest"])
    ap.add_argument("--income", action="store_true", help="add assumed distribution yields (income_assumptions.json)")
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--rate", default="DGS10", choices=["DGS3MO", "DGS2", "DGS10"],
                    help="yield used to label rising/falling blocks")
    ap.add_argument("--block", type=int, default=63, help="trading days per regime block")
    ap.add_argument("--thresh", type=float, default=0.25, help="pp change over a block to count as rising/falling")
    ap.add_argument("--portfolios", nargs="*", help="names from portfolio.json (default: all)")
    args = ap.parse_args()
    if args.cmd == "fetch":
        fetch(args.years)
    elif args.cmd == "build":
        build()
    elif args.cmd == "selftest":
        selftest()
    else:
        px, rates, _ = load_data(args.years)
        allp = json.loads(PORTFOLIO_FILE.read_text())
        report(px, rates, args, {n: allp[n] for n in (args.portfolios or allp)})


if __name__ == "__main__":
    main()
