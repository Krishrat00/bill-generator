from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
# Read from environment safely
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASS = os.getenv("MONGO_PASS")
MONGO_HOST = os.getenv("MONGO_HOST")
MONGO_DB = os.getenv("MONGO_DB")

MONGO_URI = f"mongodb+srv://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}/?appName=bill-cluster0"
MONGO_DB= MONGO_DB if MONGO_DB else "bill_app"
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]   # Use this everywhere

def get_collection(name: str):
    return db[name]
