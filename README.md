# Python Personal Finance

Flask + SQLite personal finance tracker for cash and Taiwan stock records.

## Features

- Track TWD and USD cash records.
- Track stock buy and sell records.
- Delete cash and stock records with browser confirmation.
- Show asset summary, stock holdings, transaction history, and pie charts.
- Fetch USD/TWD exchange rate and Taiwan stock prices with a short cache.
- Initialize or migrate the SQLite database safely.

## Setup

```powershell
py -m pip install -r requirements.txt
py db_setting.py
py -m flask --app index run --port 5001
```

Then open:

```text
http://127.0.0.1:5001/
```

## Notes

- Stock prices are fetched from TWSE, so this app is primarily for Taiwan-listed stocks.
- The sell calculation is a simple reduction of shares and transaction amount. It is useful for small practice projects, but it is not a full tax or realized-profit accounting system.
