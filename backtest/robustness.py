"""Robustness checks on the final book. Run from backtest/ after `python backtest.py build`:

    python robustness.py

1. The 9 Hormuz headline days (listed), then the same question with days picked mechanically
   (LNG's 10 biggest up / down days since the war started) so nobody picked the days.
2. Split-sample: how did ~13 book variants rank in the first vs second half of the 5y history?
"""
import numpy as np
import pandas as pd

import analysis as an
import backtest as bt


def main():
    rets, rf = an.prepare(5)
    book = bt.load_portfolio("final_no_adbe")
    b = bt.port_returns(rets, book)
    ex = bt.port_returns(rets, {t: w for t, w in book.items() if t != "LNG"})
    day = lambda x: rets.index[rets.index.searchsorted(pd.Timestamp(x))]

    print("=== the 9 Hormuz days (from the pasted tracker) ===")
    for lab, ds in (("escalation", an.ESCALATION), ("de-escalation", an.DEESCALATION)):
        for x in ds:
            t = day(x)
            print(f"  {lab:13s} {t.date()}  LNG {rets.loc[t, 'LNG']:+.1%}  GLD {rets.loc[t, 'GLD']:+.1%}  TBF {rets.loc[t, 'TBF']:+.1%}  book {b[t]:+.2%}")

    print("\n=== mechanical version: war period (since 2026-02-27), days chosen by LNG's own move ===")
    w = rets[rets.index >= "2026-02-27"]
    bw, ew = b[w.index], ex[w.index]
    up, dn = w["LNG"].nlargest(10).index, w["LNG"].nsmallest(10).index
    for name, idx in (("10 biggest LNG up days  ", up), ("10 biggest LNG down days", dn)):
        print(f"  {name} LNG {w.loc[idx, 'LNG'].mean():+.1%}  book {bw[idx].mean():+.2%}  book ex-LNG {ew[idx].mean():+.2%}  book<0 on {(bw[idx] < 0).sum()}/10")
    print(f"  war-period corr(LNG, rest of book) {w['LNG'].corr(ew):+.2f} (5y {rets['LNG'].corr(ex):+.2f}); beta of book to LNG {np.polyfit(w['LNG'], bw, 1)[0]:+.2f}")

    print("\n=== split-sample ranking of variants ===")
    cur = bt.load_portfolio("current_8")
    nosh = {t: x for t, x in cur.items() if t != "SHV"}
    swap = lambda drop, new, wt: {**{t: x for t, x in nosh.items() if t != drop}, new: wt}
    V = {"current_8": cur, "no SHV": nosh, "AVGO->ADBE": swap("AVGO", "ADBE", .12), "AVGO->XIC": swap("AVGO", "XIC.TO", .12),
         "AVGO->XLV": swap("AVGO", "XLV", .22), "AVGO->IEMG": swap("AVGO", "IEMG", .12), "NVDA->XIC": swap("NVDA", "XIC.TO", .10),
         "G": {"ITRI": .15, "GLD": .20, "LNG": .13, "NVDA": .12, "XLV": .12, "TBF": .10, "XIC.TO": .12, "ADBE": .06},
         "H": {"ITRI": .15, "GLD": .20, "LNG": .13, "NVDA": .12, "XLV": .12, "TBF": .10, "XIC.TO": .18},
         "I": {"ITRI": .12, "GLD": .20, "LNG": .14, "NVDA": .12, "XLV": .12, "TBF": .10, "XIC.TO": .14, "ADBE": .06},
         "J": {"ITRI": .12, "GLD": .20, "LNG": .14, "NVDA": .12, "XLV": .12, "TBF": .10, "XIC.TO": .20},
         "final": bt.load_portfolio("final"), "final_no_adbe": book}
    mid = rets.index[len(rets) // 2]
    rows = []
    for k, wt in V.items():
        tot = sum(wt.values())
        r = bt.port_returns(rets, {t: x / tot for t, x in wt.items()})
        rows.append((k, bt.stats(r[r.index <= mid], rf)["sharpe"], bt.stats(r[r.index > mid], rf)["sharpe"]))
    df = pd.DataFrame(rows, columns=["variant", "first half", "second half"]).set_index("variant")
    bm = bt.port_returns(rets, bt.BENCHMARK)
    print(f"  split at {mid.date()}")
    print(df.round(2).to_string())
    print(f"  benchmark: first half {bt.stats(bm[bm.index <= mid], rf)['sharpe']:.2f}, second half {bt.stats(bm[bm.index > mid], rf)['sharpe']:.2f}")
    print(f"  best first-half variant ({df['first half'].idxmax()}) scored {df.loc[df['first half'].idxmax(), 'second half']:.2f} in the second half; median variant {df['second half'].median():.2f}")


if __name__ == "__main__":
    main()
