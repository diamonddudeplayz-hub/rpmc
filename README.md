# rpmc

RPMC 2027 (Rotman Portfolio Management Competition) working repo.

- `RPMC _ Rotman School _ University of Toronto.pdf`: official rules page (source of truth)
- `Claude-Company rundown-20261008-2136.md`: earlier planning chat export
- `backtest/`: Sharpe backtest of the team portfolio, split by rising / falling rate periods

## Backtest

```
pip install pandas numpy yfinance
cd backtest
python backtest.py fetch --years 3     # needs internet: Yahoo (prices, USDCAD) + FRED (DGS3MO/DGS2/DGS10)
python backtest.py run --years 3       # all portfolios in portfolio.json vs RPMC benchmark and SPY
python backtest.py run --rate DGS2     # label regimes with the 2Y yield (or DGS3MO) instead of the 10Y
python backtest.py selftest            # synthetic data, pipeline check only
```

Edit `backtest/portfolio.json` to test other weights (e.g. the NVDA-or-AVGO swap the team agreed on).
Method and assumptions are in the docstring at the top of `backtest/backtest.py`.

## Rules to keep straight

The official PDF says each security/ETF must be **<= 25%** of the portfolio and cash **< 10%**,
with at least one trade every two weeks. The team notes say 20% for the position cap; the backtest
checks against 25% (PDF). Confirm with the committee if the 20% figure came from somewhere official.

Do not commit shared logins or passwords to this repo.
