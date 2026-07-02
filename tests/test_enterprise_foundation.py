import json
import os
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import app as app_module
from app import app


class FakeSMTP:
    sent_messages = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ehlo(self):
        return None

    def starttls(self):
        return None

    def login(self, username, password):
        self.username = username
        self.password = password

    def send_message(self, message):
        FakeSMTP.sent_messages.append(message)


class EnterpriseFoundationTests(unittest.TestCase):
    ADMIN_ENV = {
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "secret",
    }

    SMTP_ENV = {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "587",
        "SMTP_FROM": "BlackSea Connect <concierge@blackseaconnect.com>",
        "SMTP_USERNAME": "smtp-user",
        "SMTP_PASSWORD": "smtp-pass",
    }

    def setUp(self):
        self._cwd = os.getcwd()
        self._tmpdir = Path(self._cwd) / f".tmp_enterprise_foundation_tests_{uuid.uuid4().hex}"
        self._tmpdir.mkdir(exist_ok=True)
        os.chdir(self._tmpdir)
        self.owner_db_path = self._tmpdir / "data" / "blacksea_owner.db"
        self.ADMIN_ENV = {**self.ADMIN_ENV, "OWNER_DB_PATH": str(self.owner_db_path)}
        self.SMTP_ENV = {**self.SMTP_ENV, "OWNER_DB_PATH": str(self.owner_db_path)}
        app.config["TESTING"] = True
        app_module._PUBLIC_FORM_RATE_LIMITS.clear()
        self.client = app.test_client()

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        FakeSMTP.sent_messages.clear()

    def _auth_headers(self):
        import base64

        token = base64.b64encode(f"{self.ADMIN_ENV['ADMIN_USERNAME']}:{self.ADMIN_ENV['ADMIN_PASSWORD']}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    def _fetch_table(self, table_name):
        if not self.owner_db_path.exists():
            return []
        conn = sqlite3.connect(self.owner_db_path)
        try:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(f"SELECT * FROM {table_name}").fetchall()]
        finally:
            conn.close()

    def test_platform_admin_can_manage_organizations(self):
        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.post(
                "/admin/organizations",
                json={"name": "North Star Hospitality", "slug": "north-star"},
                headers=self._auth_headers(),
            )

            self.assertEqual(response.status_code, 201)
            payload = response.get_json()
            self.assertEqual(payload["organization"]["name"], "North Star Hospitality")
            self.assertEqual(payload["organization"]["status"], "ACTIVE")

            listing = self.client.get("/admin/organizations", headers=self._auth_headers())
            self.assertEqual(listing.status_code, 200)
            organizations = listing.get_json()["organizations"]
            self.assertTrue(any(item["slug"] == "north-star" for item in organizations))

            org_id = payload["organization"]["id"]
            suspended = self.client.post(f"/admin/organizations/{org_id}/suspend", headers=self._auth_headers())
            self.assertEqual(suspended.status_code, 200)
            self.assertEqual(suspended.get_json()["organization"]["status"], "SUSPENDED")

        audit_logs = self._fetch_table("audit_logs")
        self.assertGreaterEqual(len(audit_logs), 2)

    def test_company_admin_invite_flow_creates_user_membership_and_audit(self):
        with app.app_context():
            organization = app_module._upsert_organization({
                "name": "Blue Cove Rentals",
                "slug": "blue-cove-rentals",
            })
            company_admin = app_module._upsert_user({
                "email": "admin@bluecove.example",
                "full_name": "Mila Petrova",
                "organization_id": organization["id"],
                "status": "ACTIVE",
            })
            app_module._upsert_membership({
                "user_id": company_admin["id"],
                "organization_id": organization["id"],
                "role_key": app_module.ROLE_COMPANY_ADMIN,
                "status": "ACTIVE",
                "joined_at": app_module._utc_now_iso(),
            })
            app_module._upsert_user_role({
                "user_id": company_admin["id"],
                "organization_id": organization["id"],
                "role_key": app_module.ROLE_COMPANY_ADMIN,
                "status": "ACTIVE",
            })

        with self.client.session_transaction() as sess:
            sess[app_module.ENTERPRISE_SESSION_USER_ID_KEY] = company_admin["id"]
            sess[app_module.ENTERPRISE_SESSION_USER_EMAIL_KEY] = company_admin["email"]
            sess[app_module.ENTERPRISE_SESSION_USER_NAME_KEY] = company_admin["full_name"]
            sess[app_module.ENTERPRISE_SESSION_ORGANIZATION_ID_KEY] = organization["id"]
            sess[app_module.ENTERPRISE_SESSION_ROLE_KEY] = app_module.ROLE_COMPANY_ADMIN

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            invite_response = self.client.post(
                f"/organizations/{organization['id']}/invites",
                json={"email": "new.manager@example.com", "role": app_module.ROLE_OPERATIONS_MANAGER},
            )

        self.assertEqual(invite_response.status_code, 201)
        invite_payload = invite_response.get_json()
        self.assertTrue(invite_payload["email_sent"])
        self.assertEqual(len(FakeSMTP.sent_messages), 1)

        invitations = self._fetch_table("organization_invitations")
        self.assertEqual(len(invitations), 1)
        invitation_token = invitations[0]["token"]

        accept_response = self.client.get(f"/auth/organization-invitation/{invitation_token}")
        self.assertEqual(accept_response.status_code, 302)
        self.assertIn("/enterprise/dashboard", accept_response.headers["Location"])

        dashboard = self.client.get("/enterprise/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        dashboard_payload = dashboard.get_json()
        self.assertEqual(dashboard_payload["organization"]["id"], organization["id"])
        self.assertEqual(dashboard_payload["role"], app_module.ROLE_OPERATIONS_MANAGER)

        users = self._fetch_table("users")
        memberships = self._fetch_table("memberships")
        roles = self._fetch_table("user_roles")
        audit_logs = self._fetch_table("audit_logs")
        updated_invitations = self._fetch_table("organization_invitations")
        self.assertEqual(len(users), 2)
        self.assertEqual(len(memberships), 2)
        self.assertEqual(len(roles), 2)
        self.assertTrue(any(row["email"] == "new.manager@example.com" for row in users))
        self.assertTrue(any(row["status"] == "ACCEPTED" for row in updated_invitations))
        self.assertGreaterEqual(len(audit_logs), 2)


if __name__ == "__main__":
    unittest.main()
