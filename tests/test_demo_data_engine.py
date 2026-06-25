import base64
import os
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import app as app_module
from app import app


class DemoDataEngineTests(unittest.TestCase):
    ADMIN_ENV = {
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "secret",
    }

    def setUp(self):
        self._cwd = os.getcwd()
        self._tmpdir = Path(self._cwd) / f".tmp_demo_data_tests_{uuid.uuid4().hex}"
        self._tmpdir.mkdir(exist_ok=True)
        os.chdir(self._tmpdir)
        self.owner_db_path = self._tmpdir / "data" / "blacksea_owner.db"
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _auth_headers(self):
        token = base64.b64encode(
            f"{self.ADMIN_ENV['ADMIN_USERNAME']}:{self.ADMIN_ENV['ADMIN_PASSWORD']}".encode("utf-8")
        ).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    def _env(self):
        return {
            **self.ADMIN_ENV,
            "OWNER_DB_PATH": str(self.owner_db_path),
        }

    def _demo_counts(self):
        return {
            "owner_accounts": len(app_module._load_owner_accounts()),
            "owner_properties": len(app_module._load_owner_properties()),
            "reservations": len(app_module._load_reservations()),
            "operations_tasks": len(app_module._load_operations_tasks()),
            "professional_accounts": len(app_module._load_professional_accounts()),
            "calendar_events": len(app_module._load_calendar_events()),
            "owner_activity_events": len(app_module._load_owner_activity_events()),
            "property_activity_events": len(app_module._load_property_activity_events()),
            "operations_task_events": len(app_module._load_operations_task_events()),
        }

    def test_seed_is_idempotent_and_populates_dashboards(self):
        with app_module.app.app_context(), patch.dict(os.environ, self._env(), clear=True):
            seed_response = self.client.post("/admin/demo-data/seed", headers=self._auth_headers())
            self.assertEqual(seed_response.status_code, 302)
            self.assertIn("/admin/demo-data", seed_response.headers["Location"])

            page_response = self.client.get("/admin/demo-data", headers=self._auth_headers())
            self.assertEqual(page_response.status_code, 200)
            self.assertIn("Enterprise Demo Manager", page_response.get_data(as_text=True))

            first_counts = self._demo_counts()
            self.assertGreaterEqual(first_counts["owner_accounts"], 4)
            self.assertGreaterEqual(first_counts["owner_properties"], 12)
            self.assertGreaterEqual(first_counts["reservations"], 40)
            self.assertGreaterEqual(first_counts["operations_tasks"], 80)
            self.assertGreaterEqual(first_counts["professional_accounts"], 15)
            self.assertGreater(first_counts["calendar_events"], 0)
            self.assertGreater(first_counts["owner_activity_events"], 0)
            self.assertGreater(first_counts["property_activity_events"], 0)
            self.assertGreater(first_counts["operations_task_events"], 0)

            second_seed_response = self.client.post("/admin/demo-data/seed", headers=self._auth_headers())
            self.assertEqual(second_seed_response.status_code, 302)
            self.assertIn("message=exists", second_seed_response.headers["Location"])
            second_counts = self._demo_counts()
            self.assertEqual(first_counts, second_counts)

            dashboard = app_module._build_admin_dashboard()
            self.assertGreater(len(dashboard["executive_timeline"]), 0)
            self.assertGreater(len(dashboard["executive_alerts"]), 0)
            self.assertGreater(len(dashboard["smart_recommendations"]), 0)
            self.assertGreater(len(dashboard["property_status_cards"]), 0)
            self.assertGreater(len(dashboard["operations_heatmap"]), 0)
            self.assertGreater(dashboard["reservation_widget"]["stats"]["todays_operations"], 0)
            self.assertGreater(dashboard["reservation_widget"]["stats"]["late_operations"], 0)

            demo_owner = next(account for account in app_module._load_owner_accounts() if account.get("id") == "demo-owner-stella")
            with app.test_request_context("/owners/dashboard?lang=en"):
                owner_context = app_module._owner_portal_dashboard_context(demo_owner, [], "en")
            self.assertGreater(len(owner_context["properties"]), 0)
            self.assertGreater(len(app_module._load_reservations(owner_id=demo_owner["id"])), 0)
            self.assertGreater(len(owner_context["calendar_widget"]["upcoming_events"]), 0)

            demo_professional = next(account for account in app_module._load_professional_accounts() if account.get("id") == "demo-professional-01")
            professional_context = app_module._professional_dashboard_context(demo_professional)
            self.assertGreater(len(professional_context["assigned_tasks"]), 0)
            self.assertGreater(professional_context["total_count"], 0)
            self.assertGreaterEqual(professional_context["completed_count"], 0)

    def test_clear_removes_only_demo_records_and_keeps_real_data(self):
        with app_module.app.app_context(), patch.dict(os.environ, self._env(), clear=True):
            real_owner = app_module._upsert_owner_account({
                "id": "real-owner-1",
                "created_at": "2026-06-10T10:00:00Z",
                "full_name": "Real Owner",
                "email": "real.owner@example.com",
                "phone": "+359888000000",
                "property_type": "Villa",
                "city": "Varna",
                "property_name": "Real Sea View Villa",
                "number_of_units": 1,
                "notes": "Production row used to verify clear safety.",
                "status": "ACTIVE",
                "language": "en",
                "last_login_at": "",
                "internal_notes": "",
            })
            self.assertIsNotNone(real_owner)
            real_property = app_module._append_owner_property({
                "id": "real-property-1",
                "owner_id": "real-owner-1",
                "created_at": "2026-06-11T10:00:00Z",
                "name": "Real Sea View Villa",
                "property_type": "Villa",
                "location": "Varna",
                "bedrooms": 4,
                "bathrooms": 3,
                "guest_capacity": 8,
                "operating_mode": "year-round",
                "notes": "Production property used to verify clear safety.",
                "status": "ACTIVE",
                "guest_guide_ready": 1,
                "access_instructions_ready": 1,
                "emergency_contact_ready": 1,
                "cleaning_partner_ready": 1,
                "admin_notes": "",
            })
            self.assertIsNotNone(real_property)

            self.assertEqual(self.client.post("/admin/demo-data/seed", headers=self._auth_headers()).status_code, 302)
            self.assertIsNotNone(app_module._load_demo_manifest())
            self.assertGreaterEqual(len([account for account in app_module._load_owner_accounts() if account.get("is_demo")]), 4)

            clear_response = self.client.post("/admin/demo-data/clear", headers=self._auth_headers())
            self.assertEqual(clear_response.status_code, 302)
            self.assertIsNone(app_module._load_demo_manifest())
            self.assertEqual(len([account for account in app_module._load_owner_accounts() if account.get("is_demo")]), 0)
            self.assertEqual(len([property_record for property_record in app_module._load_owner_properties() if property_record.get("is_demo")]), 0)
            self.assertIsNotNone(app_module._find_owner_account_by_email("real.owner@example.com"))
            self.assertIsNotNone(app_module._find_owner_property("real-property-1"))


if __name__ == "__main__":
    unittest.main()
