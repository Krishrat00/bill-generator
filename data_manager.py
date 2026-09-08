import os
import re
import sqlite3
from contextlib import closing

from db import DB_BACKEND, get_collection


def normalize_text(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value.replace(".", "")).strip().upper()


def normalize_gstin(value):
    return value.strip().upper() if isinstance(value, str) else ""


def normalize_pincode(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[:6]


class DatabaseManager:
    def __init__(self, db_path="data/data.db"):
        self.db_path = os.getenv("SQLITE_PATH", db_path)
        if DB_BACKEND == "sqlite":
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            self._create_sqlite_tables()
        else:
            self.parties = get_collection("parties")
            self.transports = get_collection("transports")
            self.cities = get_collection("cities")
            self.pending = get_collection("pending_requests")
            self._create_mongo_indexes()

    def _connect(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _create_sqlite_tables(self):
        with closing(self._connect()) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS parties (
                    name TEXT PRIMARY KEY, gstin TEXT, place TEXT,
                    pincode TEXT DEFAULT '', fixed_place INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS transports (
                    name TEXT PRIMARY KEY, gstin TEXT
                );
                CREATE TABLE IF NOT EXISTS cities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, city TEXT,
                    state TEXT, pincode TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS pending_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT,
                    name TEXT, gstin TEXT, place TEXT, pincode TEXT DEFAULT ''
                );
            """)
            for table in ("parties", "cities", "pending_requests"):
                columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
                if "pincode" not in columns:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN pincode TEXT DEFAULT ''")
            conn.commit()

    def _create_mongo_indexes(self):
        self.parties.create_index("name", unique=True)
        self.transports.create_index("name", unique=True)
        self.cities.create_index([("city", 1), ("state", 1)], unique=True)
        self.pending.create_index([("type", 1), ("name", 1)], unique=True)

    def add_party(self, name, gstin="", place="", pincode="", fixed_place=False):
        name = normalize_text(name)
        document = {
            "name": name,
            "gstin": normalize_gstin(gstin),
            "place": normalize_text(place),
            "pincode": normalize_pincode(pincode),
            "fixed_place": bool(fixed_place),
        }
        if not name:
            return False
        if DB_BACKEND == "mongodb":
            self.parties.update_one({"name": name}, {"$set": document}, upsert=True)
        else:
            with closing(self._connect()) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO parties (name, gstin, place, pincode, fixed_place)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, document["gstin"], document["place"], document["pincode"], int(document["fixed_place"])))
                conn.commit()
        return True

    def get_party(self, name):
        name = normalize_text(name)
        if DB_BACKEND == "mongodb":
            row = self.parties.find_one({"name": name}, {"_id": 0})
            return row or {}
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT name, gstin, place, pincode, fixed_place FROM parties WHERE name = ?", (name,)).fetchone()
        if not row:
            return {}
        return {"name": row[0], "gstin": row[1], "place": row[2], "pincode": row[3], "fixed_place": bool(row[4])}

    def get_all_parties(self):
        if DB_BACKEND == "mongodb":
            return sorted(row["name"] for row in self.parties.find({}, {"name": 1, "_id": 0}))
        with closing(self._connect()) as conn:
            return [row[0] for row in conn.execute("SELECT name FROM parties ORDER BY name COLLATE NOCASE")]

    def add_transport(self, name, gstin=""):
        name = normalize_text(name)
        if not name:
            return False
        document = {"name": name, "gstin": normalize_gstin(gstin)}
        if DB_BACKEND == "mongodb":
            self.transports.update_one({"name": name}, {"$set": document}, upsert=True)
        else:
            with closing(self._connect()) as conn:
                conn.execute("INSERT OR REPLACE INTO transports (name, gstin) VALUES (?, ?)", (name, document["gstin"]))
                conn.commit()
        return True

    def get_transport(self, name):
        name = normalize_text(name)
        if DB_BACKEND == "mongodb":
            row = self.transports.find_one({"name": name}, {"_id": 0})
            return row or {}
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT name, gstin FROM transports WHERE name = ?", (name,)).fetchone()
        return {"name": row[0], "gstin": row[1]} if row else {}

    def get_all_transports(self):
        if DB_BACKEND == "mongodb":
            return sorted(row["name"] for row in self.transports.find({}, {"name": 1, "_id": 0}))
        with closing(self._connect()) as conn:
            return [row[0] for row in conn.execute("SELECT name FROM transports ORDER BY name COLLATE NOCASE")]

    def add_city(self, city, state, pincode=""):
        city, state, pincode = normalize_text(city), normalize_text(state), normalize_pincode(pincode)
        if not city or not state:
            return False
        document = {"city": city, "state": state, "pincode": pincode}
        if DB_BACKEND == "mongodb":
            self.cities.update_one({"city": city, "state": state}, {"$set": document}, upsert=True)
        else:
            with closing(self._connect()) as conn:
                conn.execute("""
                    INSERT INTO cities (city, state, pincode) VALUES (?, ?, ?)
                    ON CONFLICT DO NOTHING
                """, (city, state, pincode))
                conn.commit()
        return True

    def get_all_cities(self):
        if DB_BACKEND == "mongodb":
            rows = self.cities.find({}, {"city": 1, "state": 1, "_id": 0})
        else:
            with closing(self._connect()) as conn:
                rows = [{"city": city, "state": state} for city, state in conn.execute("SELECT city, state FROM cities")]
        return sorted(f"{row['city']} ({row['state']})" for row in rows)

    def add_pending(self, type_, name, gstin="", place="", pincode=""):
        name, place, pincode = normalize_text(name), normalize_text(place), normalize_pincode(pincode)
        if not name or type_ not in {"party", "transport"}:
            return False
        document = {
            "type": type_, "name": name, "gstin": normalize_gstin(gstin),
            "place": place if type_ == "party" else "",
            "pincode": pincode if type_ == "party" else "",
        }
        if DB_BACKEND == "mongodb":
            collection = self.parties if type_ == "party" else self.transports
            if collection.find_one({"name": name}) or self.pending.find_one({"type": type_, "name": name}):
                return False
            self.pending.insert_one(document)
        else:
            with closing(self._connect()) as conn:
                table = "parties" if type_ == "party" else "transports"
                if conn.execute(f"SELECT 1 FROM {table} WHERE UPPER(name)=?", (name,)).fetchone():
                    return False
                if conn.execute("SELECT 1 FROM pending_requests WHERE type=? AND UPPER(name)=?", (type_, name)).fetchone():
                    return False
                conn.execute("INSERT INTO pending_requests (type, name, gstin, place, pincode) VALUES (?, ?, ?, ?, ?)", tuple(document.values()))
                conn.commit()
        return True

    def get_all_pending(self):
        if DB_BACKEND == "mongodb":
            return list(self.pending.find({}, {"_id": 0}))
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT type, name, gstin, place, pincode FROM pending_requests ORDER BY id DESC")
            return [{"type": t, "name": n, "gstin": g, "place": p, "pincode": pin} for t, n, g, p, pin in rows]

    def approve_pending(self, type_, name):
        name = normalize_text(name)
        if DB_BACKEND == "mongodb":
            row = self.pending.find_one({"type": type_, "name": name}, {"_id": 0})
            if not row:
                return False
            if type_ == "party":
                self.add_party(name, row.get("gstin", ""), row.get("place", ""), row.get("pincode", ""))
            else:
                self.add_transport(name, row.get("gstin", ""))
            self.pending.delete_one({"type": type_, "name": name})
            return True
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT gstin, place, pincode FROM pending_requests WHERE type=? AND name=?", (type_, name)).fetchone()
            if not row:
                return False
            if type_ == "party":
                self.add_party(name, row[0], row[1], row[2])
            else:
                self.add_transport(name, row[0])
            conn.execute("DELETE FROM pending_requests WHERE type=? AND name=?", (type_, name))
            conn.commit()
        return True

    def reject_pending(self, type_, name):
        name = normalize_text(name)
        if DB_BACKEND == "mongodb":
            return self.pending.delete_one({"type": type_, "name": name}).deleted_count > 0
        with closing(self._connect()) as conn:
            cursor = conn.execute("DELETE FROM pending_requests WHERE type=? AND name=?", (type_, name))
            conn.commit()
            return cursor.rowcount > 0
