> Latest numbers are in the last section ("everything is now measured total return"). Earlier sections are kept as a log.

# Backtest results (LSEG daily data to 2026-10-08, CAD terms)

Reproduce: `cd backtest && python backtest.py build && python backtest.py run --years 5 --income`
(`--years 2` for the last two years). Portfolio = current 8 (ITRI 15, GLD 15, SHV 15, LNG 13, AVGO 12, NVDA 10, XLV 10, TBF 10).

| | Portfolio Sharpe | RPMC Benchmark Sharpe | SPY Sharpe |
|---|---|---|---|
| 5 years | 1.55 | 0.88 | 0.85 |
| 2 years | 1.15 | 1.23 | 0.98 |

Rolling 105-day windows (the length of the competition): portfolio median Sharpe 1.59 (5y) / 0.83 (2y);
it beats the benchmark in 72% of windows over 5y but only 37% over 2y.

Rate regimes (10Y yield, 63-day blocks, ex-post labels). 5y portfolio Sharpe: rising 1.83, falling 2.42, flat 1.07.
2y: rising 1.04, falling 0.30, flat 3.10 (only 7 blocks, too few to conclude anything).
TBF effect (current_8 vs the same book with SHV instead of TBF): +0.3 Sharpe in rising blocks, -0.35 in falling blocks (5y), ~+0.07 overall.

## Caveats
- LSEG exports are price-only. SHV is modelled as T-bill carry; other distributions are rough assumed yields in
  `income_assumptions.json` (benchmark Sharpe moves 0.68 -> 0.88 on this). Replace with total-return series when available.
- Holdings were picked with hindsight (NVDA, AVGO, LNG have been big winners), so the portfolio's historical Sharpe is flattered.
- Regime splits are descriptive; labels use what happened over each block, not a forecast.
- NVDA/AVGO correlation is ~0.6, ITRI ~0.27 with NVDA/AVGO/XLV. Average pairwise correlation (~0.05) is low mainly because of GLD/SHV/TBF/LNG.

## Follow-up (`python analysis.py`)
- Risk is concentrated: ITRI + NVDA + AVGO = ~80% of portfolio variance on 37% of the weight. GLD, XLV, TBF, SHV are ~0-6% each.
- ITRI is not low-vol (41% vs LNG 30%). Inverse-vol sizing would put LNG above ITRI. Pitch ITRI as conviction/catalyst-sized, not vol-sized.
- SHV barely changes Sharpe (1.55 with, 1.52 without; 2y 1.15 vs 1.14). Using the real SHV total-return export (not the T-bill carry model): in CAD terms SHV has ~6% vol from USDCAD, so it is not risk-free if the platform scores in CAD.
- Hormuz headline days (9 days from the pasted tracker): LNG +3.1% avg on escalation, -3.2% on de-escalation; TBF +0.9 / -0.6; GLD -0.4 / +1.1.
  Portfolio net: +0.5% / +0.2%, so roughly neutral to headlines.
- Sharpe by year, portfolio vs benchmark: 2022 0.29 vs -0.95, 2023 2.62 vs 1.14, 2024 3.03 vs 2.15, 2025 0.68 vs 1.32, 2026 YTD 1.21 vs 1.10.

## Update: real SHV total return, GLD, ITRI
- `shv total return.xlsx` (cumulative TR %, +19.19% over 5y; my carry model gave +20.5%) is now used for SHV. Other tickers still price-only + assumed yields.
- GLD: vol 18% (5y) / 23% (2y), above SPY's. It is a diversifier, not low-vol: avg +0.2% on SPY's worst 5% days (SPY -2.2%, NVDA -4.6%). -7.7% since Sep 3 ($410 -> $379); 52w range $362-$496.
- Variants (Sharpe 5y/2y, max drawdown 5y): current 1.55/1.15, -13.4%; SHV 10 + GLD 20: 1.58/1.20, -13.0%;
  AVGO->XIC.TO 12 + SHV 10 + GLD 20: 1.49/1.18, -9.6%. Benchmark 0.88/1.23.
- ITRI biggest daily moves, last 2y: +26.2% (2026-07-28), -21.1% (2025-10-30), -10.0% (2025-07-31). At 15% weight a -21% day is -3.2% of the portfolio.
  Now $84.23 vs $107.02 on Jul 28 and $99.66 on Jul 31.
- No ADBE price file in the repo yet, so ADBE vol/correlation is untested.

## Update: everything is now measured total return
- SHV: LSEG total-return export. NVDA, LNG, AVGO: exact total return from the dividend tables in `backtest/dividends.csv` (ex-dates, split-adjusted).
- SPY, XBB.TO, IEMG, XLV, TBF, XIC.TO: weekly total-return exports (`ROLLING PERFORMANCE*.xlsx`); weekly income spread over that week's trading days.
  Measured yields: SPY 1.33%, XLV 1.62%, IEMG 2.76%, XIC.TO 2.74%, XBB.TO 3.17%, TBF 2.85% (TBF had been counted as zero income).
- `final_no_adbe`: Sharpe 1.54 (5y) / 1.29 (2y), max drawdown -12.2% / -10.6%. RPMC benchmark: 0.89 / 1.23, -15.0% / -10.8%.
  Beats the benchmark in 80% (5y) / 49% (2y) of 105-day windows. `current_8`: 1.58 / 1.18.
- Charts in `charts/` regenerated on these numbers. `rpmc_calendar.ics` has trade-by dates and catalyst dates.

## Jiseop's book (posted Oct 9, `portfolio.json["jiseop"]`)
LLY 15, GLD 15, LNG 15, JAAA 14, RY.TO 12, WMT 8, NVDA 7, XIC.TO 6, VOO 5, EFA 3. His reported 5y monthly Sharpe 2.48 (CAGR 27%, implied vol ~9%);
our final book on the same monthly basis is 1.80 (24.3%, 10.3%); benchmark 0.90 (he got 0.88). To compare properly we need total-return exports for
LLY, WMT, RY.TO, JAAA, VOO, EFA (same layout as `shv total return.xlsx`, or weekly Rolling Performance + price files), then:
`python backtest.py build && python backtest.py run --years 5 --income --portfolios final_no_adbe jiseop`, plus `robustness.py` for the split-in-half check.
