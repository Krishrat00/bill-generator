import sqlite3, os

class DatabaseManager:
    def __init__(self, db_path="data/data.db"):
        os.makedirs("data", exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            gstin TEXT,
            pan TEXT,
            aadhar TEXT,
            place TEXT,
            fixed_place INTEGER DEFAULT 0
        )
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS transports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            gstin TEXT
        )
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT,
            state TEXT
        )
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            name TEXT,
            gstin TEXT,
            pan TEXT,
            aadhar TEXT,
            place TEXT
        )
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_name TEXT,
            account_number TEXT,
            ifsc TEXT
        )
        """)
        self.conn.commit()

    # ---------- PARTY ----------
    def get_all_parties(self):
        rows = self.conn.execute("SELECT name FROM parties ORDER BY name").fetchall()
        return [r["name"] for r in rows]

    def get_party(self, name):
        row = self.conn.execute("SELECT * FROM parties WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        return dict(row)

    def add_party(self, name, gstin="", pan="", aadhar="", place="", fixed_place=0):
        self.conn.execute("""
            INSERT OR REPLACE INTO parties (name, gstin, pan, aadhar, place, fixed_place)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, gstin, pan, aadhar, place, fixed_place))
        self.conn.commit()

    # ---------- TRANSPORT ----------
    def get_all_transports(self):
        rows = self.conn.execute("SELECT name FROM transports ORDER BY name").fetchall()
        return [r["name"] for r in rows]

    def get_transport(self, name):
        row = self.conn.execute("SELECT * FROM transports WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        return dict(row)

    # ---------- CITY ----------
    def add_city(self, city, state):
        self.conn.execute("INSERT INTO cities (city, state) VALUES (?, ?)", (city, state))
        self.conn.commit()

    # ---------- PENDING ----------
    def add_pending(self, type_, name, gstin="", pan="", aadhar="", place=""):
        self.conn.execute("""
            INSERT INTO pending_requests (type, name, gstin, pan, aadhar, place)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (type_, name, gstin, pan, aadhar, place))
        self.conn.commit()

    def get_all_pending(self):
        rows = self.conn.execute("SELECT * FROM pending_requests ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

    def approve_pending(self, type_, name):
        cur = self.conn.execute(
            "SELECT * FROM pending_requests WHERE type = ? AND name = ?",
            (type_, name)
        )
        row = cur.fetchone()
        if row:
            if row["type"] == "party":
                self.conn.execute("""
                    INSERT INTO parties (name, gstin, pan, aadhar, place)
                    VALUES (?, ?, ?, ?, ?)
                """, (row["name"], row["gstin"], row["pan"], row["aadhar"], row["place"]))

            elif row["type"] == "transport":
                self.conn.execute("""
                    INSERT INTO transports (name, gstin, place)
                    VALUES (?, ?, ?)
                """, (row["name"], row["gstin"], row["place"]))

            self.conn.execute(
                "DELETE FROM pending_requests WHERE type = ? AND name = ?",
                (type_, name)
            )
            self.conn.commit()



    def reject_pending(self, type_, name):
        self.conn.execute("DELETE FROM pending_requests WHERE type=? AND name=?", (type_, name))
        self.conn.commit()
