import sqlite3
import os
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

load_dotenv()

SQLITE_PATH = "data/data.db"
MONGO_URL = os.getenv("MONGO_URI")
if not MONGO_URL:
    user = os.getenv("MONGO_USER")
    password = os.getenv("MONGO_PASS")
    host = os.getenv("MONGO_HOST")
    MONGO_URL = f"mongodb+srv://{user}:{password}@{host}/?appName=bill-cluster0"
DB_NAME = os.getenv("MONGO_DB", "bill_app")


def migrate():
    # --- Connect SQLite ---
    sql_conn = sqlite3.connect(SQLITE_PATH)
    sql_conn.row_factory = sqlite3.Row
    cur = sql_conn.cursor()

    def rows_with_optional_pincode(table, columns):
        existing = {row[1] for row in cur.execute(f"PRAGMA table_info({table})")}
        selected = ["'' AS pincode" if column == "pincode" and column not in existing else column for column in columns]
        return cur.execute(f"SELECT {', '.join(selected)} FROM {table}")

    # --- Connect Mongo ---
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    parties = db["parties"]
    transports = db["transports"]
    cities = db["cities"]
    pending = db["pending_requests"]

    # Create indexes
    parties.create_index([("name", ASCENDING)], unique=True)
    transports.create_index([("name", ASCENDING)], unique=True)
    cities.create_index([("city", ASCENDING), ("state", ASCENDING)], unique=True)
    pending.create_index([("type", ASCENDING), ("name", ASCENDING)], unique=True)

    print("Migrating parties...")
    for row in rows_with_optional_pincode("parties", ["name", "gstin", "place", "pincode", "fixed_place"]):
        parties.update_one(
            {"name": row["name"]},
            {"$set": {
                "gstin": row["gstin"],
                "place": row["place"],
                "pincode": row["pincode"],
                "fixed_place": bool(row["fixed_place"])
            }},
            upsert=True
        )

    print("Migrating transports...")
    for row in cur.execute("SELECT name, gstin FROM transports"):
        transports.update_one(
            {"name": row["name"]},
            {"$set": {"gstin": row["gstin"]}},
            upsert=True
        )

    print("Migrating cities...")
    for row in rows_with_optional_pincode("cities", ["city", "state", "pincode"]):
        cities.update_one(
            {"city": row["city"], "state": row["state"]},
            {"$setOnInsert": {
                "city": row["city"],
                "state": row["state"],
                "pincode": row["pincode"]
            }},
            upsert=True
        )

    print("Migrating pending requests...")
    for row in rows_with_optional_pincode("pending_requests", ["type", "name", "gstin", "place", "pincode"]):
        pending.update_one(
            {"type": row["type"], "name": row["name"]},
            {"$set": {
                "gstin": row["gstin"],
                "place": row["place"],
                "pincode": row["pincode"]
            }},
            upsert=True
        )

    print("\n🎉 Migration completed successfully!")
    sql_conn.close()


if __name__ == "__main__":
    migrate()
