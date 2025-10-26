import json
import os

class DataManager:
    def __init__(self, base_dir="data"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

        self.party_file = os.path.join(base_dir, "parties.json")
        self.transport_file = os.path.join(base_dir, "transports.json")
        self.city_file = os.path.join(base_dir, "cities.json")
        self.pending_file = os.path.join(base_dir, "pending_requests.json")

        self.parties = self._load_json(self.party_file) or {}
        self.transports = self._load_json(self.transport_file) or {}
        self.cities = self._load_json(self.city_file) or {}
        self.pending_requests = self._load_json(self.pending_file) or {}

    # ---------- JSON Helpers ----------
    def _load_json(self, file):
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def _save_json(self, data, file):
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    # ---------- Normalization ----------
    def _norm(self, name):
        return name.strip().upper() if isinstance(name, str) else ""

    # ---------------- Parties ---------------- #
    def add_party(self, name, gstin="", place="", fixed_place=False):
        key = self._norm(name)
        if not key:
            return False
        self.parties[key] = {
            "name": name.strip(),
            "gstin": (gstin or "").strip(),
            "place": (place or "").strip(),
            "fixed_place": bool(fixed_place)
        }
        self._save_json(self.parties, self.party_file)
        return True

    def get_party(self, name):
        key = self._norm(name)
        return self.parties.get(key, {})

    def get_all_parties(self):
        return sorted([v.get("name", k) for k, v in self.parties.items()])

    # ---------------- Transports ---------------- #
    def add_transport(self, name, gstin=""):
        key = self._norm(name)
        if not key:
            return False
        self.transports[key] = {
            "name": name.strip(),
            "gstin": (gstin or "").strip()
        }
        self._save_json(self.transports, self.transport_file)
        return True

    def get_transport(self, name):
        key = self._norm(name)
        return self.transports.get(key, {})

    def get_all_transports(self):
        return sorted([v.get("name", k) for k, v in self.transports.items()])

    # ---------------- Cities ---------------- #
    def add_city(self, city, state):
        if not city or not state:
            return False
        state = state.strip()
        city = city.strip()
        if state not in self.cities:
            self.cities[state] = []
        existing = [c.lower() for c in self.cities[state]]
        if city.lower() not in existing:
            self.cities[state].append(city)
            self.cities[state].sort(key=str.lower)
            self._save_json(self.cities, self.city_file)
        return True

    def get_all_cities(self):
        result = []
        for state, city_list in self.cities.items():
            abbrev = "".join([w[0].upper() + "." for w in state.split()])
            for city in city_list:
                result.append(f"{city} ({abbrev})")
        return sorted(result)

    def get_raw_cities(self):
        return self.cities

    # ---------------- Pending Requests ---------------- #
    def _save_pending(self):
        self._save_json(self.pending_requests, self.pending_file)

    def add_pending(self, type_, name, gstin="", place=""):
    # Check if already exists in parties/transports
        key_norm = self._norm(name)
        if type_ == "party" and key_norm in self.parties:
            return False  # ignore existing party
        if type_ == "transport" and key_norm in self.transports:
            return False  # ignore existing transport

        # Check if already in pending
        pending_key = f"{type_}:{name.strip()}"
        if pending_key in self.pending_requests:
            return False

        self.pending_requests[pending_key] = {
            "type": type_,
            "name": name.strip(),
            "gstin": gstin.strip(),
            "place": place.strip() if type_=="party" else "",
        }
        self._save_pending()
        return True


    def get_all_pending(self):
        return list(self.pending_requests.values())

    def approve_pending(self, key):
        entry = self.pending_requests.pop(key, None)
        if not entry:
            return False
        if entry["type"] == "party":
            self.add_party(entry["name"], entry.get("gstin",""), entry.get("place",""))
        else:
            self.add_transport(entry["name"], entry.get("gstin",""))
        self._save_pending()
        return True

    def reject_pending(self, key):
        if key in self.pending_requests:
            self.pending_requests.pop(key)
            self._save_pending()
            return True
        return False
