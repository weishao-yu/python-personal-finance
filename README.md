# Python Personal Finance

A small Flask + SQLite personal finance app for tracking cash and Taiwan stock records.

## Features

- Track TWD and USD cash records.
- Track Taiwan stock buy and sell records.
- Delete cash and stock records with browser confirmation.
- Show total assets, cash value, stock market value, stock holdings, and transaction history.
- Generate asset allocation pie charts.
- Fetch USD/TWD exchange rate and Taiwan stock prices.
- Cache external API results for 5 minutes to reduce repeated requests.
- Initialize and migrate the SQLite database safely.

## Setup

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

Initialize or update the database:

```powershell
py db_setting.py
```

Run the app:

```powershell
py -m flask --app index run --port 5000
```

Open:

```text
http://127.0.0.1:5000/
```

## Files

- `index.py`: Flask routes, calculations, validation, API fetching, and chart generation.
- `db_setting.py`: Creates or updates the SQLite tables.
- `templates/`: HTML pages.
- `static/`: Generated chart images.
- `datafile.db`: Local SQLite database.

## Notes

- Stock prices are fetched from TWSE, so this app is mainly for Taiwan-listed stocks.
- Sell records reduce the share count and cost amount in a simple way. This is useful for a practice project, but it is not full realized-profit or tax accounting.
- If you publish this project publicly, consider whether you want to include `datafile.db`, because it may contain your personal finance records.
