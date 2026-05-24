import sqlite3


conn = sqlite3.connect("datafile.db")
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
conn.close()
