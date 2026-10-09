# rpmc

RPMC 2027 (Rotman Portfolio Management Competition) working repo.

- `RPMC _ Rotman School _ University of Toronto.pdf`: official rules page (source of truth)
- `Claude-Company rundown-20261008-2136.md`: earlier planning chat export
- `backtest/`: Sharpe backtest of the team portfolio, split by rising / falling rate periods

## Backtest

LSEG exports sit in the repo root (daily price files, `shv total return.xlsx`, six weekly `ROLLING PERFORMANCE*.xlsx` total-return files, `adobe.xlsx`);
NVDA / LNG / AVGO total return comes from `backtest/dividends.csv`.

```
pip install pandas numpy openpyxl pypdf matplotlib
cd backtest
python backtest.py build                 # xlsx -> data/*.csv (prints the measured income yields)
python backtest.py run --years 5 --income --portfolios current_8 final_no_adbe     # Sharpe by rate regime vs RPMC benchmark
python analysis.py                       # risk contributions, swap options, GLD and Hormuz event checks
python robustness.py                     # mechanical Hormuz days, split-sample ranking of variants
python order_sheet.py --price NVDA=231.4 --fx 1.419      # share counts on CAD 1,000,000 (live-price overrides)
python charts.py                         # PNGs in ../charts/
```

Books live in `backtest/portfolio.json` (`final_no_adbe` is the proposed one). `rpmc_calendar.ics` has the trade-by dates and catalysts.
Method and assumptions are in the docstring at the top of `backtest/backtest.py`; results log in `backtest/RESULTS.md`.

## Rules to keep straight

The RPMC page and the PDF both say each security/ETF must be **<= 25%** of the portfolio (the team notes' 20% is not in the rules; the proposed book tops out at 19% anyway),
cash **< 10%** from Oct 9, and at least one trade every two weeks (penalty otherwise). The benchmark is struck at the Oct 9 closing prices.
The page says "most" S&P 500 / TSX Composite names plus "a few major ETFs" are tradable, so check ITRI, TBF, XLV and XIC.TO are available on RPM before ordering.

Do not commit shared logins or passwords to this repo.
