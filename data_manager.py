from db import get_collection
from pymongo import ASCENDING
from bson.objectid import ObjectId

class DatabaseManager:
    def __init__(self):
        self.parties   = get_collection("parties")
        self.transports = get_collection("transports")
        self.cities    = get_collection("cities")
        self.pending   = get_collection("pending_requests")

        self._create_indexes()

    # ------------------ Indexes ------------------
    def _create_indexes(self):
        self.parties.create_index([("name", ASCENDING)], unique=True)
        self.transports.create_index([("name", ASCENDING)], unique=True)
        self.cities.create_index(
            [("city", ASCENDING), ("state", ASCENDING)], unique=True
        )
        self.pending.create_index(
            [("type", ASCENDING), ("name", ASCENDING)], unique=True
        )

    # ------------------ Helpers ------------------
    def _norm(self, name):
        return name.strip().upper() if isinstance(name, str) else ""

    # ------------------ Parties ------------------
    def add_party(self, name, gstin="", place="", fixed_place=False):
        if not name:
            return False

        self.parties.update_one(
            {"name": name.strip()},
            {
                "$set": {
                    "gstin": gstin.strip(),
                    "place": place.strip(),
                    "fixed_place": bool(fixed_place)
                }
            },
            upsert=True
        )
        return True

    def get_party(self, name):
        row = self.parties.find_one({"name": name})
        if not row:
            return {}

        return {
            "name": row["name"],
            "gstin": row.get("gstin", ""),
            "place": row.get("place", ""),
            "fixed_place": row.get("fixed_place", False)
        }

    def get_all_parties(self):
        return sorted([p["name"] for p in self.parties.find({}, {"name": 1})])

    # ------------------ Transports ------------------
    def add_transport(self, name, gstin=""):
        if not name:
            return False

        self.transports.update_one(
            {"name": name.strip()},
            {"$set": {"gstin": gstin.strip()}},
            upsert=True
        )
        return True

    def get_transport(self, name):
        row = self.transports.find_one({"name": name})
        if not row:
            return {}
        return {"name": row["name"], "gstin": row.get("gstin", "")}

    def get_all_transports(self):
        return sorted([t["name"] for t in self.transports.find({}, {"name": 1})])

    # ------------------ Cities ------------------
    def add_city(self, city, state):
        if not city or not state:
            return False

        self.cities.update_one(
            {"city": city.strip(), "state": state.strip()},
            {"$setOnInsert": {"city": city.strip(), "state": state.strip()}},
            upsert=True
        )
        return True

    def get_all_cities(self):
        cities = list(self.cities.find({}, {"city": 1, "state": 1}))
        result = []
        for c in cities:
            abbrev = "".join([w[0].upper() + "." for w in c["state"].split()])
            result.append(f"{c['city']} ({abbrev})")
        return sorted(result)

    # ------------------ Pending Requests ------------------
    def add_pending(self, type_, name, gstin="", place=""):
        if not name:
            return False

        key = name.strip()

        # Already exists in main table?
        if type_ == "party" and self.parties.find_one({"name": key}):
            return False
        if type_ == "transport" and self.transports.find_one({"name": key}):
            return False

        # Already pending?
        if self.pending.find_one({"type": type_, "name": key}):
            return False

        self.pending.insert_one({
            "type": type_,
            "name": key,
            "gstin": gstin.strip(),
            "place": place.strip() if type_ == "party" else ""
        })
        return True

    def get_all_pending(self):
        return list(self.pending.find({}, {"_id": 0}).sort("_id", -1))

    def approve_pending(self, type_, name):
        key = name.strip()
        row = self.pending.find_one({"type": type_, "name": key})
        if not row:
            return False

        if type_ == "party":
            self.add_party(key, row.get("gstin", ""), row.get("place", ""))
        else:
            self.add_transport(key, row.get("gstin", ""))

        self.pending.delete_one({"type": type_, "name": key})
        return True

    def reject_pending(self, type_, name):
        self.pending.delete_one({"type": type_, "name": name.strip()})
        return True
