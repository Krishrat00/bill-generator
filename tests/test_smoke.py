import os
import tempfile
import unittest


DB_FILE = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DB_BACKEND"] = "sqlite"
os.environ["SQLITE_PATH"] = DB_FILE

from app import app, data_manager


class SmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True, SECRET_KEY="test-secret")
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        try:
            os.remove(DB_FILE)
        except FileNotFoundError:
            pass

    def test_home_and_party_listing(self):
        data_manager.add_party("  surat   . textiles", "24ABCDE1234F1ZY", "surat (gujarat)", "395010")
        data_manager.add_transport("fast   . transport", "24ABCDE1234F1ZY")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SURAT TEXTILES", response.data)
        self.assertIn(b"FAST TRANSPORT", response.data)

    def test_pending_approve_and_reject(self):
        response = self.client.post("/add_pending", json={
            "type": "party",
            "name": "new   . party",
            "gstin": "24abcde1234f1zy",
            "place": "surat (gujarat)",
            "pincode": "395010",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data_manager.approve_pending("party", "NEW PARTY"))
        self.assertEqual(data_manager.get_party("new party")["pincode"], "395010")

        response = self.client.post("/add_pending", json={
            "type": "transport",
            "name": "reject   . transport",
            "gstin": "24abcde1234f1zy",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data_manager.reject_pending("transport", "REJECT TRANSPORT"))

    def test_admin_add_and_delete(self):
        response = self.client.post("/admin/add", json={
            "table": "cities",
            "city": "surat",
            "state": "gujarat",
            "pincode": "395010",
        })
        self.assertEqual(response.status_code, 200)
        rows = self.client.get("/admin/data?table=cities").get_json()
        row = next(item for item in rows if item["city"] == "SURAT")
        response = self.client.post("/admin/delete", json={"table": "cities", "id": row["id"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "deleted")

    def test_bill_download(self):
        response = self.client.post("/download", data={
            "bill_no": "TEST-001",
            "date": "2026-09-08",
            "customer_name": "SURAT TEXTILES",
            "ch_no": "SURAT (GUJARAT)",
            "pincode": "395010",
            "gstin": "24ABCDE1234F1ZY",
            "transport": "FAST TRANSPORT",
            "transport_gstin": "24ABCDE1234F1ZY",
            "item_name[]": ["COTTON"],
            "qty[]": ["2"],
            "unit[]": ["Mtr"],
            "rate[]": ["100"],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertTrue(response.data.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
