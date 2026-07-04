import os
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import app as app_module
from app import app


class DemoOwnerCliTests(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._tmpdir = Path(self._cwd) / f".tmp_demo_owner_cli_{uuid.uuid4().hex}"
        self._tmpdir.mkdir(exist_ok=True)
        os.chdir(self._tmpdir)
        self.owner_db_path = self._tmpdir / "data" / "blacksea_owner.db"
        app.config["TESTING"] = True
        self.runner = app.test_cli_runner()
        self.client = app.test_client()

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _env(self, **overrides):
        values = {
            "APP_ENV": "development",
            "OWNER_DB_PATH": str(self.owner_db_path),
        }
        values.update(overrides)
        return values

    def test_seed_demo_owner_is_idempotent_and_magic_link_uses_normal_auth(self):
        with app.app_context(), patch.dict(os.environ, self._env(), clear=True):
            first = self.runner.invoke(
                args=["seed-demo-owner", "--magic-link", "--base-url", "http://127.0.0.1:5000"]
            )
            self.assertEqual(first.exit_code, 0, first.output)
            self.assertIn("Demo owner ready: demo.owner@blackseaconnect.com", first.output)
            self.assertIn("Seeded 2 properties, 3 service requests, and 2 reservations.", first.output)
            self.assertIn("http://127.0.0.1:5000/auth/owner-magic/", first.output)

            owner = app_module._find_owner_account_by_email("demo.owner@blackseaconnect.com")
            self.assertIsNotNone(owner)
            self.assertEqual(owner["full_name"], "Demo Owner")
            self.assertIn("role=owner", owner["internal_notes"])

            properties = app_module._owner_properties_for_account(owner["id"])
            self.assertEqual(len(properties), 2)

            service_requests = [
                record
                for record in app_module._load_service_requests()
                if record.get("owner_email") == "demo.owner@blackseaconnect.com"
            ]
            self.assertEqual(len(service_requests), 3)
            self.assertTrue(all(record.get("timeline") for record in service_requests))

            reservations = app_module._load_reservations(owner_id=owner["id"])
            self.assertEqual(len(reservations), 2)
            self.assertTrue(all(record.get("arrival_datetime") for record in reservations))
            self.assertTrue(all(record.get("departure_datetime") for record in reservations))
            self.assertGreaterEqual(len(app_module._load_owner_activity_events(owner["id"])), 3)

            tokens = app_module._load_owner_magic_tokens()
            self.assertEqual(len(tokens), 1)
            login_response = self.client.get(f"/auth/owner-magic/{tokens[0]['token']}?lang=en")
            self.assertEqual(login_response.status_code, 302)
            self.assertIn("/owners/dashboard", login_response.headers["Location"])
            with self.client.session_transaction() as owner_session:
                self.assertTrue(owner_session.get(app_module.OWNER_SESSION_LOGGED_IN_KEY))
                self.assertEqual(
                    owner_session.get(app_module.OWNER_SESSION_EMAIL_KEY),
                    "demo.owner@blackseaconnect.com",
                )

            second = self.runner.invoke(args=["seed-demo-owner"])
            self.assertEqual(second.exit_code, 0, second.output)
            self.assertEqual(len(app_module._owner_properties_for_account(owner["id"])), 2)
            self.assertEqual(
                len([
                    record
                    for record in app_module._load_service_requests()
                    if record.get("owner_email") == "demo.owner@blackseaconnect.com"
                ]),
                3,
            )
            self.assertEqual(len(app_module._load_reservations(owner_id=owner["id"])), 2)

    def test_seed_demo_owner_refuses_production_without_explicit_opt_in(self):
        with app.app_context(), patch.dict(
            os.environ,
            self._env(APP_ENV="production"),
            clear=True,
        ):
            result = self.runner.invoke(args=["seed-demo-owner", "--magic-link"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("disabled in production", result.output)
            self.assertIsNone(
                app_module._find_owner_account_by_email("demo.owner@blackseaconnect.com")
            )
            self.assertEqual(app_module._load_owner_magic_tokens(), [])


if __name__ == "__main__":
    unittest.main()
