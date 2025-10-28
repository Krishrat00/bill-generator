import os
import json
import sqlite3

def migrate_json_to_sqlite(json_dir="data", db_path="data/data.db"):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create tables (same as DataManager)
    c.execute("""
        CREATE TABLE IF NOT EXISTS parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            gstin TEXT,
            place TEXT,
            fixed_place INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS transports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            gstin TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT,
            state TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS pending_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            name TEXT,
            gstin TEXT,
            place TEXT
        )
    """)

    # Helper function
    def load_json(filename):
        path = os.path.join(json_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    # Migrate Parties
    parties = load_json("parties.json")
    for k, v in parties.items():
        c.execute("""
            INSERT OR IGNORE INTO parties (name, gstin, place, fixed_place)
            VALUES (?, ?, ?, ?)
        """, (
            v.get("name", k),
            v.get("gstin", ""),
            v.get("place", ""),
            int(v.get("fixed_place", False))
        ))

    # Migrate Transports
    transports = load_json("transports.json")
    for k, v in transports.items():
        c.execute("""
            INSERT OR IGNORE INTO transports (name, gstin)
            VALUES (?, ?)
        """, (
            v.get("name", k),
            v.get("gstin", "")
        ))

    # Migrate Cities
    cities = load_json("cities.json")
    for state, city_list in cities.items():
        for city in city_list:
            c.execute("""
                INSERT INTO cities (city, state)
                VALUES (?, ?)
            """, (city, state))

    # Migrate Pending Requests
    pending = load_json("pending_requests.json")
    for k, v in pending.items():
        c.execute("""
            INSERT INTO pending_requests (type, name, gstin, place)
            VALUES (?, ?, ?, ?)
        """, (
            v.get("type", ""),
            v.get("name", ""),
            v.get("gstin", ""),
            v.get("place", "")
        ))

    conn.commit()
    conn.close()

    print("✅ Migration complete! Data successfully moved to", db_path)


if __name__ == "__main__":
    migrate_json_to_sqlite()
