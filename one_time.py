import sqlite3

conn = sqlite3.connect("data/data.db")  # your existing DB
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS bank_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_name TEXT NOT NULL,
    account_number TEXT NOT NULL,
    ifsc TEXT NOT NULL
)
""")

conn.commit()
conn.close()