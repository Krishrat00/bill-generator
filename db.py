import os
import sqlite3
from contextlib import closing

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

DB_BACKEND = os.getenv("DB_BACKEND", "mongodb").lower()
SQLITE_PATH = os.getenv("SQLITE_PATH", "data/data.db")


class SQLiteCollection:
    def __init__(self, name):
        self.name = name
        self._create_tables()

    def _connect(self):
        return sqlite3.connect(SQLITE_PATH, check_same_thread=False)

    def _create_tables(self):
        os.makedirs(os.path.dirname(SQLITE_PATH) or ".", exist_ok=True)
        with closing(self._connect()) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS bank_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bank_name TEXT,
                    account_number TEXT,
                    ifsc TEXT
                );
            """)
            conn.commit()

    def find(self, query=None, projection=None):
        query = query or {}
        columns = "*"
        result_names = None
        if projection:
            selected = [key for key, include in projection.items() if include and key != "_id"]
            if selected:
                columns = ", ".join(selected)
                result_names = selected
        where = " AND ".join(f"{key} = ?" for key in query)
        sql = f"SELECT {columns} FROM {self.name}"
        if where:
            sql += f" WHERE {where}"
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, tuple(query.values())).fetchall()
            names = result_names or [column[1] for column in conn.execute(f"PRAGMA table_info({self.name})")]
        return [dict(zip(names, row)) for row in rows]

    def insert_one(self, document):
        fields = [key for key in document if key not in {"_id", "table"}]
        placeholders = ", ".join("?" for _ in fields)
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.name} ({', '.join(fields)}) VALUES ({placeholders})",
                tuple(document[field] for field in fields),
            )
            conn.commit()
            return type("InsertResult", (), {"inserted_id": cursor.lastrowid})()

    def delete_one(self, query):
        field, value = next(iter(query.items()))
        field = "id" if field == "_id" else field
        with closing(self._connect()) as conn:
            cursor = conn.execute(f"DELETE FROM {self.name} WHERE {field} = ?", (value,))
            conn.commit()
            return type("DeleteResult", (), {"deleted_count": cursor.rowcount})()

    def create_index(self, *_args, **_kwargs):
        return None


if DB_BACKEND == "sqlite":
    client = None
    db = None

    def get_collection(name):
        return SQLiteCollection(name)
else:
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        user = os.getenv("MONGO_USER")
        password = os.getenv("MONGO_PASS")
        host = os.getenv("MONGO_HOST")
        if not all((user, password, host)):
            raise RuntimeError("Set MONGO_URI or MONGO_USER, MONGO_PASS, and MONGO_HOST")
        mongo_uri = f"mongodb+srv://{user}:{password}@{host}/?appName=bill-cluster0"

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client[os.getenv("MONGO_DB", "bill_app")]

    def get_collection(name):
        return db[name]
