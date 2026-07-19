import os
import re
import shutil
import unittest
import uuid
from pathlib import Path

import app as app_module
from app import app


class ProfessionalOfflineOperationsTests(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.temp_dir = Path(self.original_cwd) / f".tmp_pwa_offline_{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        os.chdir(self.temp_dir)
        app.config["TESTING"] = True
        self.client = app.test_client()
        with app.app_context():
            self.professional = app_module._upsert_professional_account({
                "id": "professional-offline",
                "created_at": "2026-07-19T08:00:00Z",
                "full_name": "Offline Professional",
                "email": "offline-professional@example.com",
                "phone": "+359888000001",
                "company": "Field Operations",
                "service_categories": "Maintenance",
                "status": "ACTIVE",
                "last_login_at": "",
            })
            self.task = app_module._upsert_operations_task_from_source({
                "id": "offline-task",
                "request_id": "offline-task",
                "source_id": "offline-task",
                "source_type": "TEST",
                "created_at": "2026-07-19T08:00:00Z",
                "updated_at": "2026-07-19T08:00:00Z",
                "title": "Offline field task",
                "category": "MAINTENANCE",
                "owner_id": "owner-offline",
                "owner_name": "Owner Offline",
                "owner_email": "owner@example.com",
                "property_id": "property-offline",
                "property_name": "Offline Villa",
                "property_location": "Varna",
                "assigned_to": "Offline Professional",
                "assigned_professional_id": self.professional["id"],
                "priority": "NORMAL",
                "status": "ASSIGNED",
                "due_date": "2026-07-19",
                "notes": "Follow the field instructions.",
                "admin_notes": "",
            })
        with self.client.session_transaction() as session_data:
            session_data[app_module.PROFESSIONAL_SESSION_LOGGED_IN_KEY] = True
            session_data[app_module.PROFESSIONAL_SESSION_ID_KEY] = self.professional["id"]
            session_data[app_module.PROFESSIONAL_SESSION_EMAIL_KEY] = self.professional["email"]

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _headers(self, key, version=None, **extra):
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "X-Idempotency-Key": key,
            "X-Task-Version": version or self.task["updated_at"],
        }
        headers.update(extra)
        return headers

    def test_idempotent_replay_does_not_duplicate_transition(self):
        headers = self._headers("offline-accept-0001")
        first = self.client.post("/professionals/tasks/offline-task", data={"task_action": "accept"}, headers=headers)
        replay = self.client.post("/professionals/tasks/offline-task", data={"task_action": "accept"}, headers=headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.get_json()["duplicate"])
        self.assertEqual(app_module._find_operations_task("offline-task")["status"], "ACCEPTED")
        events = app_module._load_operations_task_events("offline-task")
        self.assertEqual(sum(event["event_type"] == "professional_accepted" for event in events), 1)
        self.assertEqual(sum(event["event_type"] == "pwa_mutation_receipt" for event in events), 1)

    def test_version_conflict_is_reported_without_overwrite(self):
        app_module._operations_task_update_json_fields("offline-task", updated_at="2026-07-19T09:00:00Z")
        response = self.client.post(
            "/professionals/tasks/offline-task",
            data={"task_action": "accept"},
            headers=self._headers("offline-conflict-0001"),
        )

        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertTrue(payload["conflict"])
        self.assertEqual(payload["error"], "task_version_conflict")
        self.assertEqual(payload["server_version"], "2026-07-19T09:00:00Z")
        self.assertEqual(app_module._find_operations_task("offline-task")["status"], "ASSIGNED")

    def test_keep_local_resolution_replays_with_idempotency(self):
        app_module._operations_task_update_json_fields("offline-task", updated_at="2026-07-19T09:00:00Z")
        response = self.client.post(
            "/professionals/tasks/offline-task",
            data={"task_action": "accept"},
            headers=self._headers("offline-resolution-0001", **{"X-Conflict-Resolution": "keep-local"}),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(app_module._find_operations_task("offline-task")["status"], "ACCEPTED")
        self.assertTrue(response.get_json()["server_version"])

    def test_invalid_idempotency_key_is_rejected(self):
        response = self.client.post(
            "/professionals/tasks/offline-task",
            data={"task_action": "accept"},
            headers=self._headers("bad"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "idempotency_key_invalid")

    def test_concurrent_replay_is_retryable_and_does_not_run_twice(self):
        key = "offline-concurrent-0001"
        receipt_seed = f"{self.professional['id']}:{key}".encode("utf-8")
        receipt_id = f"pwa-{app_module.hashlib.sha256(receipt_seed).hexdigest()}"
        self.assertTrue(app_module._reserve_professional_pwa_mutation("offline-task", receipt_id, key, "ASSIGNED"))

        response = self.client.post(
            "/professionals/tasks/offline-task",
            data={"task_action": "accept"},
            headers=self._headers(key),
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.get_json()["retryable"])
        self.assertEqual(app_module._find_operations_task("offline-task")["status"], "ASSIGNED")

    def test_task_page_exposes_offline_snapshot_without_credentials(self):
        response = self.client.get("/professionals/tasks/offline-task")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="pwa-task-config"', body)
        self.assertIn('"ownerContact"', body)
        self.assertIn('"propertyInformation"', body)
        self.assertNotIn("session_cookie", body)
        self.assertNotIn("magic_token", body)


class OfflineEngineSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(app.root_path)
        cls.storage = (cls.root / "static/js/pwa-storage.js").read_text(encoding="utf-8")
        cls.operations = (cls.root / "static/js/pwa-operations.js").read_text(encoding="utf-8")
        cls.worker = (cls.root / "static/service-worker.js").read_text(encoding="utf-8")
        cls.runtime = (cls.root / "templates/partials/pwa_runtime.html").read_text(encoding="utf-8")

    def test_indexeddb_has_dedicated_task_queue_upload_conflict_and_draft_stores(self):
        self.assertIn('DB_NAME = "blacksea-professional-offline"', self.storage)
        for store_name in ("tasks", "mutations", "uploads", "conflicts", "drafts"):
            self.assertIn(f'"{store_name}"', self.storage)
        self.assertNotIn("localStorage", self.storage + self.operations)

    def test_queue_records_ordering_idempotency_retry_and_payload(self):
        for field in ("idempotencyKey", "retryCount", "payload", "taskId", "createdAt", "timestamp"):
            self.assertRegex(self.operations, rf"\b{field}\b")
        self.assertIn("localeCompare", self.storage)
        self.assertIn("backoffDelay", self.operations)
        self.assertIn("X-Idempotency-Key", self.operations)

    def test_offline_checklist_completion_and_uploads_are_persisted(self):
        self.assertIn("updateChecklistUi", self.operations)
        self.assertIn("putDraft", self.operations)
        self.assertIn("removeDraft", self.operations)
        self.assertIn("value instanceof File", self.operations)
        self.assertIn("putUpload", self.operations)
        self.assertIn("blob: file", self.operations)
        self.assertIn("pwa-queued-uploads", self.operations)

    def test_conflict_resolution_supports_all_required_choices(self):
        self.assertIn('response.status === 409', self.operations)
        self.assertIn('data-resolution="keep-local"', self.operations)
        self.assertIn('data-resolution="keep-server"', self.operations)
        self.assertIn('data-resolution="retry"', self.operations)

    def test_reconnect_background_sync_and_foreground_fallback_exist(self):
        self.assertIn('addEventListener("online"', self.operations)
        self.assertIn('registration.sync.register(SYNC_TAG)', self.operations)
        self.assertIn('event.tag === "blacksea-professional-sync"', self.worker)
        self.assertIn("backgroundSyncQueue", self.worker)

    def test_logout_clears_cache_and_indexeddb(self):
        self.assertIn("clearAll", self.operations)
        self.assertIn("clearOfflineDatabase", self.worker)
        self.assertIn("CLEAR_PRIVATE_CACHES", self.worker)

    def test_private_responses_remain_outside_service_worker_cache(self):
        self.assertIn('request.method !== "GET"', self.worker)
        self.assertIn('contentType.includes("application/json")', self.worker)
        for excluded in ("/api/", "/auth/", "/admin", "/owners/finance/", "/professionals/stripe/"):
            self.assertIn(f'"{excluded}"', self.worker)

    def test_runtime_loads_storage_before_operations_and_network_ui(self):
        sources = re.findall(r"filename='([^']+)'", self.runtime)
        self.assertEqual(sources, ["js/pwa-storage.js", "js/pwa-operations.js", "js/pwa.js"])


if __name__ == "__main__":
    unittest.main()
