import sqlite3
import os
import re
from contextlib import closing

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
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._create_tables()

    # ---------- Connection Helper ----------
    def _connect(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    # ---------- Table Creation ----------
    def _create_tables(self):
        with closing(self._connect()) as conn:
            cur = conn.cursor()

            cur.execute("""
            CREATE TABLE IF NOT EXISTS parties (
                name TEXT PRIMARY KEY,
                gstin TEXT,
                place TEXT,
                pincode TEXT DEFAULT '',
                fixed_place INTEGER DEFAULT 0
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS transports (
                name TEXT PRIMARY KEY,
                gstin TEXT
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS cities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city TEXT,
                state TEXT,
                pincode TEXT DEFAULT ''
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                name TEXT,
                gstin TEXT,
                place TEXT,
                pincode TEXT DEFAULT ''
            )
            """)

            for table in ("parties", "cities", "pending_requests"):
                columns = [row[1] for row in cur.execute(f"PRAGMA table_info({table})")]
                if "pincode" not in columns:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN pincode TEXT DEFAULT ''")

            for rowid, name, gstin, place, pincode in cur.execute("SELECT rowid, name, gstin, place, pincode FROM parties").fetchall():
                cur.execute("UPDATE parties SET name = ?, gstin = ?, place = ?, pincode = ? WHERE rowid = ?", (normalize_text(name), normalize_gstin(gstin), normalize_text(place), normalize_pincode(pincode), rowid))
            for rowid, name, gstin in cur.execute("SELECT rowid, name, gstin FROM transports").fetchall():
                cur.execute("UPDATE transports SET name = ?, gstin = ? WHERE rowid = ?", (normalize_text(name), normalize_gstin(gstin), rowid))
            for rowid, city, state, pincode in cur.execute("SELECT rowid, city, state, pincode FROM cities").fetchall():
                cur.execute("UPDATE cities SET city = ?, state = ?, pincode = ? WHERE rowid = ?", (normalize_text(city), normalize_text(state), normalize_pincode(pincode), rowid))
            for rowid, name, gstin, place, pincode in cur.execute("SELECT rowid, name, gstin, place, pincode FROM pending_requests").fetchall():
                cur.execute("UPDATE pending_requests SET name = ?, gstin = ?, place = ?, pincode = ? WHERE rowid = ?", (normalize_text(name), normalize_gstin(gstin), normalize_text(place), normalize_pincode(pincode), rowid))

            conn.commit()

    # ---------- Normalization ----------
    def _norm(self, name):
        return normalize_text(name).upper()

    # ---------- Party Methods ----------
    def add_party(self, name, gstin="", place="", pincode="", fixed_place=False):
        name = normalize_text(name)
        place = normalize_text(place)
        pincode = normalize_pincode(pincode)
        if not name:
            return False
        with closing(self._connect()) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO parties (name, gstin, place, pincode, fixed_place)
                VALUES (?, ?, ?, ?, ?)
            """, (name, normalize_gstin(gstin), place, pincode, int(fixed_place)))
            conn.commit()
        return True

    def get_party(self, name):
        name = normalize_text(name)
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT name, gstin, place, pincode, fixed_place FROM parties WHERE name = ?", (name,))
            row = cur.fetchone()
        if not row: return {}
        return {"name": row[0], "gstin": row[1], "place": row[2], "pincode": row[3], "fixed_place": bool(row[4])}

    def get_all_parties(self):
        return sorted([p["name"] for p in self.parties.find({}, {"name": 1})])

    # ------------------ Transports ------------------
    def add_transport(self, name, gstin=""):
        name = normalize_text(name)
        if not name:
            return False
        with closing(self._connect()) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO transports (name, gstin)
                VALUES (?, ?)
            """, (name, normalize_gstin(gstin)))
            conn.commit()
        return True

    def get_transport(self, name):
        name = normalize_text(name)
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT name, gstin FROM transports WHERE name = ?", (name,))
            row = cur.fetchone()
        if not row: return {}
        return {"name": row[0], "gstin": row[1]}

    def get_all_transports(self):
        return sorted([t["name"] for t in self.transports.find({}, {"name": 1})])

    # ---------- City Methods ----------
    def add_city(self, city, state, pincode=""):
        city = normalize_text(city)
        state = normalize_text(state)
        pincode = normalize_pincode(pincode)
        if not city or not state:
            return False
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT id FROM cities WHERE lower(city)=lower(?) AND lower(state)=lower(?)", (city, state))
            if cur.fetchone() is None:
                conn.execute("INSERT INTO cities (city, state, pincode) VALUES (?, ?, ?)", (city, state, pincode))
                conn.commit()
        return True

    def get_all_cities(self):
        cities = list(self.cities.find({}, {"city": 1, "state": 1}))
        result = []
        for c in cities:
            abbrev = "".join([w[0].upper() + "." for w in c["state"].split()])
            result.append(f"{c['city']} ({abbrev})")
        return sorted(result)

    # ---------- Pending Requests ----------
    def add_pending(self, type_, name, gstin="", place="", pincode=""):
        name = normalize_text(name)
        place = normalize_text(place)
        pincode = normalize_pincode(pincode)
        with closing(self._connect()) as conn:

            key_norm = self._norm(name)
            if not key_norm:
                return False

            # --- Check if already exists in party or transport tables ---
            if type_ == "party":
                existing = conn.execute("SELECT 1 FROM parties WHERE UPPER(name)=?", (key_norm,)).fetchone()
            elif type_ == "transport":
                existing = conn.execute("SELECT 1 FROM transports WHERE UPPER(name)=?", (key_norm,)).fetchone()
            else:
                return False

            if existing:
                # Already exists — skip adding to pending
                return False

            # --- Check if already pending ---
            pending = conn.execute(
                "SELECT 1 FROM pending_requests WHERE type=? AND UPPER(name)=?",
                (type_, key_norm)
            ).fetchone()

            if pending:
                # Already pending — skip again
                return False

            # --- Add new pending request ---
            conn.execute(
                """
                INSERT INTO pending_requests (type, name, gstin, place, pincode)
                VALUES (?, ?, ?, ?, ?)
                """,
                (type_, name, normalize_gstin(gstin), place if type_ == "party" else "", pincode if type_ == "party" else "")
            )
            conn.commit()
            return True


    def get_all_pending(self):
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT type, name, gstin, place, pincode FROM pending_requests ORDER BY id DESC")
            return [{"type": t, "name": n, "gstin": g, "place": p, "pincode": pin} for t, n, g, p, pin in cur.fetchall()]

    def approve_pending(self, type_, name):
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT gstin, place, pincode FROM pending_requests WHERE type=? AND name=?", (type_, name))
            row = cur.fetchone()
            if not row:
                return False
            gstin, place, pincode = row
            if type_ == "party":
                self.add_party(name, gstin, place, pincode)
            else:
                self.add_transport(name, gstin)
            conn.execute("DELETE FROM pending_requests WHERE type=? AND name=?", (type_, name))
            conn.commit()
        return True

    def reject_pending(self, type_, name):
        self.pending.delete_one({"type": type_, "name": name.strip()})
        return True
