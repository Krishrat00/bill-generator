# db.py
import sqlite3

DB_PATH = "data/data.db"  # adjust path if different

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
