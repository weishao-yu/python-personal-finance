from flask import Flask, flash, g, redirect, render_template, request
import math
import os
import sqlite3
import time

import matplotlib
matplotlib.use("agg")
import matplotlib.pyplot as plt
import requests


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

database = "datafile.db"
DEFAULT_USD_TWD_RATE = 32.0
CACHE_SECONDS = 300
price_cache = {}


@app.template_filter("money")
def money(value):
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return value


def get_db():
    if not hasattr(g, "sqlite_db"):
        g.sqlite_db = sqlite3.connect(database)
        ensure_schema(g.sqlite_db)
    return g.sqlite_db


@app.teardown_appcontext
def close_connection(exception):
    if hasattr(g, "sqlite_db"):
        g.sqlite_db.close()


def ensure_schema(conn):
    cursor = conn.cursor()
    cursor.execute(
        """create table if not exists cash (
            transaction_id integer primary key,
            taiwanese_dollars integer,
            us_dollars real,
            note varchar(30),
            date_info date
        )"""
    )
    cursor.execute(
        """create table if not exists stock (
            transaction_id integer primary key,
            stock_id varchar(10),
            stock_num integer,
            stock_price real,
            processing_fee integer,
            tax integer,
            date_info date,
            trade_type varchar(10) default 'buy'
        )"""
    )
    columns = [row[1] for row in cursor.execute("pragma table_info(stock)").fetchall()]
    if "trade_type" not in columns:
        cursor.execute("alter table stock add column trade_type varchar(10) default 'buy'")
    conn.commit()


def to_int(value, default=0):
    if value in (None, ""):
        return default
    return int(value)


def to_float(value, default=0.0):
    if value in (None, ""):
        return default
    return float(value)


def cached_get(cache_key, fetcher):
    now = time.time()
    cached = price_cache.get(cache_key)
    if cached and now - cached["time"] < CACHE_SECONDS:
        return cached["value"]
    value = fetcher()
    price_cache[cache_key] = {"value": value, "time": now}
    return value


def get_usd_twd_rate():
    def fetch_rate():
        response = requests.get("https://tw.rter.info/capi.php", timeout=5)
        response.raise_for_status()
        currency = response.json()
        return float(currency["USDTWD"]["Exrate"])

    try:
        return cached_get("usd_twd", fetch_rate), None
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return DEFAULT_USD_TWD_RATE, "匯率資料暫時無法更新，目前使用預設匯率。"


def get_current_stock_price(stock_id):
    def fetch_price():
        response = requests.get(
            "https://www.twse.com.tw/exchangeReport/STOCK_DAY",
            params={"response": "json", "stockNo": stock_id},
            timeout=5,
        )
        response.raise_for_status()
        rows = response.json().get("data") or []
        if not rows:
            raise ValueError("No stock price data")
        return float(str(rows[-1][6]).replace(",", ""))

    return cached_get(f"stock:{stock_id}", fetch_price)


def remove_file(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def save_pie_chart(path, labels, sizes):
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", shadow=None)
    fig.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=0, wspace=0)
    plt.savefig(path, dpi=200)
    plt.close(fig)


def stock_trade_label(trade_type):
    return "賣出" if trade_type == "sell" else "買進"


def calculate_stock_summary(cursor, stock_id):
    rows = cursor.execute("select * from stock where stock_id =?", (stock_id,)).fetchall()
    shares = 0
    stock_cost = 0

    for row in rows:
        trade_type = row[7] if len(row) > 7 and row[7] else "buy"
        quantity = row[2] or 0
        price = row[3] or 0
        fee = row[4] or 0
        tax = row[5] or 0
        amount = quantity * price + fee + tax

        if trade_type == "sell":
            shares -= quantity
            stock_cost -= amount
        else:
            shares += quantity
            stock_cost += amount

    return shares, stock_cost


@app.route("/")
def home():
    conn = get_db()
    cursor = conn.cursor()

    cash_result = cursor.execute("select * from cash order by transaction_id desc").fetchall()
    taiwanese_dollars = sum(row[1] or 0 for row in cash_result)
    us_dollars = sum(row[2] or 0 for row in cash_result)

    currency, currency_error = get_usd_twd_rate()
    cash_total = math.floor(taiwanese_dollars + us_dollars * currency)

    stock_result = cursor.execute("select * from stock order by transaction_id desc").fetchall()
    unique_stock_list = []
    for row in stock_result:
        if row[1] not in unique_stock_list:
            unique_stock_list.append(row[1])

    total_stock_value = 0
    stock_info = []
    stock_errors = []

    for stock_id in unique_stock_list:
        shares, stock_cost = calculate_stock_summary(cursor, stock_id)
        if shares <= 0:
            continue

        try:
            current_price = get_current_stock_price(stock_id)
        except (requests.RequestException, KeyError, TypeError, ValueError):
            stock_errors.append(stock_id)
            continue

        total_value = round(current_price * shares)
        total_stock_value += total_value
        average_cost = round(stock_cost / shares, 2) if shares else 0
        rate_of_return = round((total_value - stock_cost) * 100 / stock_cost, 2) if stock_cost else 0

        stock_info.append({
            "stock_id": stock_id,
            "shares": shares,
            "current_price": current_price,
            "total_value": total_value,
            "stock_cost": stock_cost,
            "average_cost": average_cost,
            "rate_of_return": rate_of_return,
        })

    for stock in stock_info:
        stock["value_percentage"] = round(
            stock["total_value"] * 100 / total_stock_value, 2
        ) if total_stock_value else 0

    if stock_info:
        save_pie_chart(
            "static/piechart.jpg",
            [stock["stock_id"] for stock in stock_info],
            [stock["total_value"] for stock in stock_info],
        )
    else:
        remove_file("static/piechart.jpg")

    if taiwanese_dollars or us_dollars or total_stock_value:
        save_pie_chart(
            "static/piechart2.jpg",
            ("USD", "TWD", "Stock"),
            (us_dollars * currency, taiwanese_dollars, total_stock_value),
        )
    else:
        remove_file("static/piechart2.jpg")

    data = {
        "show_pic_1": os.path.exists("static/piechart.jpg"),
        "show_pic_2": os.path.exists("static/piechart2.jpg"),
        "chart_version": int(time.time()),
        "currency": currency,
        "currency_error": currency_error,
        "stock_errors": stock_errors,
        "td": taiwanese_dollars,
        "ud": us_dollars,
        "cash_total": cash_total,
        "total_stock_value": total_stock_value,
        "total_assets": cash_total + total_stock_value,
        "cash_result": cash_result,
        "stock_result": stock_result,
        "stock_info": stock_info,
        "stock_trade_label": stock_trade_label,
    }
    return render_template("index.html", data=data)


@app.route("/cash")
def cash_form():
    return render_template("cash.html")


@app.route("/cash", methods=["POST"])
def submit_cash():
    try:
        taiwanese_dollars = to_int(request.values.get("taiwanese-dollars"))
        us_dollars = to_float(request.values.get("us-dollars"))
    except ValueError:
        flash("金額格式不正確。", "danger")
        return redirect("/cash")

    if taiwanese_dollars < 0 or us_dollars < 0:
        flash("金額不可小於 0。", "danger")
        return redirect("/cash")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """insert into cash (taiwanese_dollars, us_dollars, note, date_info)
           values (?, ?, ?, ?)""",
        (
            taiwanese_dollars,
            us_dollars,
            request.values.get("note", ""),
            request.values.get("date", ""),
        ),
    )
    conn.commit()
    flash("現金紀錄已新增。", "success")
    return redirect("/")


@app.route("/cash-delete", methods=["POST"])
def cash_delete():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("delete from cash where transaction_id=?", (request.values["id"],))
    conn.commit()
    flash("現金紀錄已刪除。", "success")
    return redirect("/")


@app.route("/stock")
def stock_form():
    return render_template("stock.html")


@app.route("/stock", methods=["POST"])
def submit_stock():
    stock_id = request.values.get("stock-id", "").strip()
    trade_type = request.values.get("trade-type", "buy")
    if not stock_id:
        flash("請輸入股票代號。", "danger")
        return redirect("/stock")

    if trade_type not in ("buy", "sell"):
        flash("交易類型不正確。", "danger")
        return redirect("/stock")

    try:
        stock_num = to_int(request.values.get("stock-num"))
        stock_price = to_float(request.values.get("stock-price"))
        processing_fee = to_int(request.values.get("processing-fee"))
        tax = to_int(request.values.get("tax"))
    except ValueError:
        flash("股票資料格式不正確。", "danger")
        return redirect("/stock")

    if stock_num <= 0 or stock_price < 0 or processing_fee < 0 or tax < 0:
        flash("股數必須大於 0，價格、手續費與交易稅不可小於 0。", "danger")
        return redirect("/stock")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """insert into stock
           (stock_id, stock_num, stock_price, processing_fee, tax, date_info, trade_type)
           values (?, ?, ?, ?, ?, ?, ?)""",
        (
            stock_id,
            stock_num,
            stock_price,
            processing_fee,
            tax,
            request.values.get("date", ""),
            trade_type,
        ),
    )
    conn.commit()
    flash("股票紀錄已新增。", "success")
    return redirect("/")


@app.route("/stock-delete", methods=["POST"])
def stock_delete():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("delete from stock where transaction_id=?", (request.values["id"],))
    conn.commit()
    flash("股票紀錄已刪除。", "success")
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
