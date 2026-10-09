# Backtest results (LSEG daily data to 2026-10-08, CAD terms)

Reproduce: `cd backtest && python backtest.py build && python backtest.py run --years 5 --income`
(`--years 2` for the last two years). Portfolio = current 8 (ITRI 15, GLD 15, SHV 15, LNG 13, AVGO 12, NVDA 10, XLV 10, TBF 10).

| | Portfolio Sharpe | RPMC Benchmark Sharpe | SPY Sharpe |
|---|---|---|---|
| 5 years | 1.51 | 0.88 | 0.85 |
| 2 years | 1.14 | 1.23 | 0.98 |

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
