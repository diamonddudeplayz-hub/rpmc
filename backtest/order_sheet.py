"""Share counts for a book on the starting CAD cash. Prices default to the last LSEG close in data/prices.csv.

    python order_sheet.py                                   # final_no_adbe, CAD 1,000,000
    python order_sheet.py --price NVDA=231.4 LNG=280 --fx 1.4190     # override with live prices in the morning
    python order_sheet.py --book final --capital 1000000

Whole shares, rounded down. USD tickers are converted at USDCAD; .TO tickers are CAD.
"""
import argparse

import pandas as pd

import backtest as bt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="final_no_adbe")
    ap.add_argument("--capital", type=float, default=1_000_000)
    ap.add_argument("--price", nargs="*", default=[], help="TICKER=price in the ticker's own currency")
    ap.add_argument("--fx", type=float, help="USDCAD override")
    a = ap.parse_args()

    px = bt.load_data(5)[0]
    last = px.ffill().iloc[-1]
    over = dict(p.split("=") for p in a.price)
    fx = a.fx or float(last["USDCAD"])
    w = bt.load_portfolio(a.book)
    rows = []
    for t, wt in sorted(w.items(), key=lambda kv: -kv[1]):
        cad = t.endswith(".TO")
        price = float(over.get(t, last[t]))
        unit = price * (1 if cad else fx)
        shares = int(wt * a.capital // unit)
        rows.append({"ticker": t, "ccy": "CAD" if cad else "USD", "target %": wt * 100, "price": price, "shares": shares,
                     "cost CAD": shares * unit, "actual %": shares * unit / a.capital * 100})
    df = pd.DataFrame(rows)
    cash = a.capital - df["cost CAD"].sum()
    print(f"book {a.book}, capital CAD {a.capital:,.0f}, USDCAD {fx:.4f}")
    print(df.round({"target %": 1, "price": 2, "cost CAD": 0, "actual %": 2}).to_string(index=False))
    print(f"\nleftover cash CAD {cash:,.0f} ({cash / a.capital:.2%}); rule: cash must stay under 10%. Largest position {df['actual %'].max():.1f}% (PDF cap 25%).")
    df.to_csv(bt.HERE.parent / "order_sheet.csv", index=False)


if __name__ == "__main__":
    main()
