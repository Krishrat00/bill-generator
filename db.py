from pymongo import MongoClient
from urllib.parse import quote_plus
import os

# Read from environment safely
MONGO_USER = quote_plus(os.getenv("MONGO_USER", "ac_db_user"))
MONGO_PASS = quote_plus(os.getenv("MONGO_PASS", "a3_db"))
MONGO_HOST = os.getenv("MONGO_HOST", "bill-cluster0.urojeoa.mongodb.net")
MONGO_DB   = os.getenv("MONGO_DB", "")

MONGO_URI = f"mongodb+srv://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}/?appName=bill-cluster0"
MONGO_DB= MONGO_DB if MONGO_DB else "bill_app"
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]   # Use this everywhere

def get_collection(name: str):
    return db[name]
