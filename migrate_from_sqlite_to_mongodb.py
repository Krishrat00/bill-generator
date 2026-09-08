import sqlite3
from pymongo import MongoClient, ASCENDING

SQLITE_PATH = "data/data.db"
MONGO_URL = ""
DB_NAME = "bill_app"


def migrate():
    # --- Connect SQLite ---
    sql_conn = sqlite3.connect(SQLITE_PATH)
    sql_conn.row_factory = sqlite3.Row
    cur = sql_conn.cursor()

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
    for row in cur.execute("SELECT name, gstin, place, fixed_place FROM parties"):
        parties.update_one(
            {"name": row["name"]},
            {"$set": {
                "gstin": row["gstin"],
                "place": row["place"],
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
    for row in cur.execute("SELECT city, state FROM cities"):
        cities.update_one(
            {"city": row["city"], "state": row["state"]},
            {"$setOnInsert": {
                "city": row["city"],
                "state": row["state"]
            }},
            upsert=True
        )

    print("Migrating pending requests...")
    for row in cur.execute("SELECT type, name, gstin, place FROM pending_requests"):
        pending.update_one(
            {"type": row["type"], "name": row["name"]},
            {"$set": {
                "gstin": row["gstin"],
                "place": row["place"]
            }},
            upsert=True
        )

    print("\n🎉 Migration completed successfully!")
    sql_conn.close()


if __name__ == "__main__":
    migrate()
