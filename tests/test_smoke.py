import os
import json
import tempfile
import unittest
from datetime import datetime, timezone


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

    def test_admin_bulk_approve_requires_admin_and_reports_results(self):
        data_manager.add_pending("party", "BULK PARTY", "24ABCDE1234F1ZY", "SURAT", "395010")
        data_manager.add_pending("transport", "BULK TRANSPORT", "24ABCDE1234F1ZY")
        requests_to_approve = [
            {"type": "party", "name": "BULK PARTY"},
            {"type": "transport", "name": "BULK TRANSPORT"},
            {"type": "unknown", "name": "INVALID"},
        ]

        with self.client.session_transaction() as session:
            session.pop("admin", None)
        response = self.client.post("/admin/approve-bulk", json={"requests": requests_to_approve})
        self.assertEqual(response.status_code, 401)

        with self.client.session_transaction() as session:
            session["admin"] = True
        response = self.client.post("/admin/approve-bulk", json={"requests": requests_to_approve})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["approved"], 2)
        self.assertEqual(len(response.get_json()["failed"]), 1)
        self.assertEqual(data_manager.get_party("BULK PARTY")["pincode"], "395010")
        self.assertEqual(data_manager.get_transport("BULK TRANSPORT")["name"], "BULK TRANSPORT")

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

    def test_admin_analytics_requires_login_and_shows_recent_totals(self):
        data_manager.save_bill("ANALYTICS-001", {"party_name": "SURAT TEXTILES"}, 300)
        data_manager.save_bill("ANALYTICS-002", {"party_name": "OTHER PARTY"}, 200)
        data_manager.save_bill("ANALYTICS-003", {"party_name": "SURAT TEXTILES"}, 100)
        response = self.client.get("/admin/analytics")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.location)

        with self.client.session_transaction() as session:
            session["admin"] = True
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        response = self.client.get(f"/admin/analytics?view=month&month={current_month}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Party-wise amount", response.data)
        self.assertIn(b"Billed amount by day", response.data)
        self.assertIn(b"Daily amounts", response.data)
        self.assertIn(b"ANALYTICS-001", response.data)
        self.assertIn(b"SURAT TEXTILES", response.data)
        self.assertIn(b"400.00", response.data)
        self.assertIn(b"600.00", response.data)
        self.assertIn(b'id="bill-count">3</span>', response.data)

        current_year = datetime.now(timezone.utc).year
        yearly_response = self.client.get(f"/admin/analytics?view=year&year={current_year}")
        self.assertEqual(yearly_response.status_code, 200)
        self.assertIn(b"Billed amount by month", yearly_response.data)
        self.assertIn(b"Monthly amounts", yearly_response.data)
        self.assertIn(b"id=\"bill-count\">3</span>", yearly_response.data)

    def test_bill_period_query_returns_more_than_recent_limit(self):
        now = datetime.now(timezone.utc)
        start_at = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_at.month == 12:
            end_at = start_at.replace(year=start_at.year + 1, month=1)
        else:
            end_at = start_at.replace(month=start_at.month + 1)

        for index in range(55):
            data_manager.save_bill(
                f"PERIOD-{index:03d}",
                {"party_name": "MONTHLY PARTY"},
                10,
            )

        bills = data_manager.get_bills_between(start_at, end_at)
        period_fixtures = [bill for bill in bills if bill["invoice_no"].startswith("PERIOD-")]
        self.assertEqual(len(period_fixtures), 55)

    def test_analytics_hides_zero_amount_days(self):
        zero_date = datetime(2026, 9, 1, tzinfo=timezone.utc)
        billed_date = datetime(2026, 9, 2, tzinfo=timezone.utc)
        with data_manager._connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO bills (invoice_no, bill_json, total_value, created_at)
                   VALUES (?, ?, ?, ?)""",
                [
                    ("ZERO-DAY-001", json.dumps({"party_name": "ZERO PARTY"}), 0, zero_date.isoformat()),
                    ("BILLED-DAY-001", json.dumps({"party_name": "BILLED PARTY"}), 125, billed_date.isoformat()),
                ],
            )

        with self.client.session_transaction() as session:
            session["admin"] = True
        response = self.client.get("/admin/analytics?view=month&month=2026-09")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        daily_table = html.split('<section class="dates"', 1)[1].split('<section class="parties"', 1)[0]
        self.assertNotIn("01 Sep 2026", daily_table)
        self.assertIn("02 Sep 2026", daily_table)
        self.assertIn("₹125.00", daily_table)

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
