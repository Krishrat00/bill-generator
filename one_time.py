import sqlite3

conn = sqlite3.connect("data/data.db")  # your existing DB
cursor = conn.cursor()

cursor.execute("""
ALTER TABLE pending_requests ADD COLUMN aadhar TEXT;
""")

conn.commit()
conn.close()