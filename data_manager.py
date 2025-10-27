import sqlite3
import os
from contextlib import closing

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
                state TEXT
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                name TEXT,
                gstin TEXT,
                place TEXT
            )
            """)

            conn.commit()

    # ---------- Normalization ----------
    def _norm(self, name):
        return name.strip().upper() if isinstance(name, str) else ""

    # ---------- Party Methods ----------
    def add_party(self, name, gstin="", place="", fixed_place=False):
        if not name:
            return False
        with closing(self._connect()) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO parties (name, gstin, place, fixed_place)
                VALUES (?, ?, ?, ?)
            """, (name.strip(), gstin.strip(), place.strip(), int(fixed_place)))
            conn.commit()
        return True

    def get_party(self, name):
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT name, gstin, place, fixed_place FROM parties WHERE name = ?", (name,))
            row = cur.fetchone()
        if not row: return {}
        return {"name": row[0], "gstin": row[1], "place": row[2], "fixed_place": bool(row[3])}

    def get_all_parties(self):
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT name FROM parties ORDER BY name COLLATE NOCASE")
            return [r[0] for r in cur.fetchall()]

    # ---------- Transport Methods ----------
    def add_transport(self, name, gstin=""):
        if not name:
            return False
        with closing(self._connect()) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO transports (name, gstin)
                VALUES (?, ?)
            """, (name.strip(), gstin.strip()))
            conn.commit()
        return True

    def get_transport(self, name):
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT name, gstin FROM transports WHERE name = ?", (name,))
            row = cur.fetchone()
        if not row: return {}
        return {"name": row[0], "gstin": row[1]}

    def get_all_transports(self):
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT name FROM transports ORDER BY name COLLATE NOCASE")
            return [r[0] for r in cur.fetchall()]

    # ---------- City Methods ----------
    def add_city(self, city, state):
        if not city or not state:
            return False
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT id FROM cities WHERE lower(city)=lower(?) AND lower(state)=lower(?)", (city, state))
            if cur.fetchone() is None:
                conn.execute("INSERT INTO cities (city, state) VALUES (?, ?)", (city, state))
                conn.commit()
        return True

    def get_all_cities(self):
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT city, state FROM cities")
            result = []
            for c, s in cur.fetchall():
                abbrev = "".join([w[0].upper() + "." for w in s.split()])
                result.append(f"{c} ({abbrev})")
        return sorted(result)

    # ---------- Pending Requests ----------
    def add_pending(self, type_, name, gstin="", place=""):
        with closing(self._connect()) as conn:

            key_norm = name.strip().upper()
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
                INSERT INTO pending_requests (type, name, gstin, place)
                VALUES (?, ?, ?, ?)
                """,
                (type_, name.strip(), gstin.strip(), place.strip() if type_ == "party" else "")
            )
            conn.commit()
            return True


    def get_all_pending(self):
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT type, name, gstin, place FROM pending_requests ORDER BY id DESC")
            return [{"type": t, "name": n, "gstin": g, "place": p} for t, n, g, p in cur.fetchall()]

    def approve_pending(self, type_, name):
        with closing(self._connect()) as conn:
            cur = conn.execute("SELECT gstin, place FROM pending_requests WHERE type=? AND name=?", (type_, name))
            row = cur.fetchone()
            if not row:
                return False
            gstin, place = row
            if type_ == "party":
                self.add_party(name, gstin, place)
            else:
                self.add_transport(name, gstin)
            conn.execute("DELETE FROM pending_requests WHERE type=? AND name=?", (type_, name))
            conn.commit()
        return True

    def reject_pending(self, type_, name):
        with closing(self._connect()) as conn:
            conn.execute("DELETE FROM pending_requests WHERE type=? AND name=?", (type_, name))
            conn.commit()
        return True
