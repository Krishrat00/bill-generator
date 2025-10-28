import sqlite3
from tabulate import tabulate  # pip install tabulate for nice table print

DB_PATH = "data/data.db"

def show_table(table):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f"SELECT * FROM {table}")
    rows = c.fetchall()
    col_names = [description[0] for description in c.description]
    conn.close()

    print(f"\n📘 {table.upper()} ({len(rows)} rows)")
    print(tabulate(rows, headers=col_names, tablefmt="grid"))

def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in c.fetchall()]
    conn.close()

    for table in tables:
        show_table(table)

if __name__ == "__main__":
    main()
