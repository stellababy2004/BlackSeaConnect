import base64
import os
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import app as app_module
from app import app


class OperationsRoutingTests(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmpdir = Path(self.cwd) / f".tmp_operations_routing_{uuid.uuid4().hex}"
        self.tmpdir.mkdir()
        os.chdir(self.tmpdir)
        self.db_path = self.tmpdir / "data" / "blacksea_owner.db"
        self.env = {
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "secret",
            "OWNER_DB_PATH": str(self.db_path),
        }
        self.env_patch = patch.dict(os.environ, self.env, clear=True)
        self.env_patch.start()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        self.env_patch.stop()
        os.chdir(self.cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def auth_headers(self):
        token = base64.b64encode(b"admin:secret").decode("ascii")
        return {"Authorization": f"Basic {token}"}

    def create_task(self, task_id, *, request_id=None, source_id=None, category="Cleaning"):
        return app_module._upsert_operations_task({
            "id": task_id,
            "request_id": request_id or task_id,
            "source_type": "RESERVATION" if source_id else "ADMIN_OPERATION",
            "source_id": source_id or task_id,
            "created_at": "2026-07-19T08:00:00+00:00",
            "updated_at": "2026-07-19T08:00:00+00:00",
            "title": category,
            "category": category,
            "status": "NEW",
            "due_date": "2026-07-19",
        }, notify=False)

    def test_board_and_detail_use_canonical_task_id(self):
        self.create_task("canonical-task", request_id="source-request")
        response = self.client.get("/admin/operations", headers=self.auth_headers())
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/admin/operations/canonical-task"', html)
        self.assertNotIn('href="/admin/operations/source-request"', html)
        self.assertEqual(
            self.client.get("/admin/operations/canonical-task", headers=self.auth_headers()).status_code,
            200,
        )

    def test_invalid_source_id_gets_localized_branded_404(self):
        response = self.client.get("/admin/operations/missing?lang=fr", headers=self.auth_headers())
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 404)
        self.assertIn("Opération introuvable", html)
        self.assertNotIn("Task not found.", html)
        self.assertNotIn("missing", html)

    def test_ambiguous_source_id_is_never_selected(self):
        self.create_task("task-a", source_id="reservation-shared", category="Arrival Cleaning")
        self.create_task("task-b", source_id="reservation-shared", category="Welcome Pack")
        response = self.client.get("/admin/operations/reservation-shared", headers=self.auth_headers())
        self.assertEqual(response.status_code, 404)

    def test_known_legacy_composite_redirects_only_when_unique(self):
        self.create_task("canonical-checkin", source_id="reservation-one", category="Check-in Preparation")
        response = self.client.get(
            "/admin/operations/reservation-one:checkin-preparation",
            headers=self.auth_headers(),
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/operations/canonical-checkin", response.headers["Location"])

    def test_calendar_navigation_rejects_stale_task_and_uses_reservation_context(self):
        reservation = {
            "id": "reservation-context",
            "created_at": "2026-07-19T08:00:00+00:00",
            "updated_at": "2026-07-19T08:00:00+00:00",
            "arrival_datetime": "2026-07-19T15:00:00+00:00",
            "departure_datetime": "2026-07-20T11:00:00+00:00",
            "status": "CONFIRMED",
            "metadata": {},
        }
        with patch.object(app_module, "_find_reservation", return_value=reservation):
            with app.test_request_context("/admin/calendar"):
                navigation = app_module._operations_navigation({
                    "id": "calendar-event",
                    "operation_task_id": "stale-task",
                    "metadata": {"reservation_id": reservation["id"]},
                }, source_kind="calendar", tasks=[])
        self.assertEqual(navigation["kind"], "reservation")
        self.assertEqual(navigation["href"], "/admin/reservations/reservation-context")
        self.assertFalse(navigation["canonical_task_id"])

    def test_legacy_request_primary_key_keeps_all_reservation_tasks(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE operations_tasks (
                    request_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    title TEXT NOT NULL
                )
            """)
        reservation = {
            "id": "reservation-legacy",
            "created_at": "2026-07-19T08:00:00+00:00",
            "updated_at": "2026-07-19T08:00:00+00:00",
            "arrival_datetime": "2026-07-19T15:00:00+00:00",
            "departure_datetime": "2026-07-22T11:00:00+00:00",
            "status": "CONFIRMED",
            "owner_id": "owner-one",
            "metadata": {},
        }
        tasks = app_module._ensure_reservation_operations_tasks(reservation)
        self.assertEqual(len(tasks), 4)
        self.assertEqual(len({task["id"] for task in tasks}), 4)
        self.assertTrue(all(task["request_id"] == task["id"] for task in tasks))


if __name__ == "__main__":
    unittest.main()
