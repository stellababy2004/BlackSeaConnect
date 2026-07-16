from datetime import datetime, timedelta, timezone
import os
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import app as app_module
from app import app


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._tmpdir = Path(self._cwd) / f".tmp_workspace_tests_{uuid.uuid4().hex}"
        self._tmpdir.mkdir(exist_ok=True)
        os.chdir(self._tmpdir)
        self.owner_db_path = self._tmpdir / "data" / "blacksea_owner.db"
        app.config["TESTING"] = True
        app_module._PUBLIC_FORM_RATE_LIMITS.clear()
        self.client = app.test_client()

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _env(self):
        return {"OWNER_DB_PATH": str(self.owner_db_path)}

    def _set_enterprise_session(self, user, organization, role_key):
        with self.client.session_transaction() as sess:
            sess[app_module.ENTERPRISE_SESSION_USER_ID_KEY] = user["id"]
            sess[app_module.ENTERPRISE_SESSION_USER_EMAIL_KEY] = user["email"]
            sess[app_module.ENTERPRISE_SESSION_USER_NAME_KEY] = user["full_name"]
            sess[app_module.ENTERPRISE_SESSION_ORGANIZATION_ID_KEY] = organization["id"]
            sess[app_module.ENTERPRISE_SESSION_ROLE_KEY] = role_key

    def _seed_workspace_user(self, organization, email, full_name, role_key):
        user = app_module._upsert_user({
            "email": email,
            "full_name": full_name,
            "organization_id": organization["id"],
            "status": "ACTIVE",
        })
        app_module._upsert_membership({
            "user_id": user["id"],
            "organization_id": organization["id"],
            "role_key": role_key,
            "status": "ACTIVE",
            "joined_at": app_module._utc_now_iso(),
        })
        return user

    def _seed_owner_property(self, owner_id, property_id, organization_id, name, location):
        app_module._append_owner_property({
            "id": property_id,
            "owner_id": owner_id,
            "organization_id": organization_id,
            "created_at": app_module._utc_now_iso(),
            "name": name,
            "property_type": "Villa",
            "location": location,
            "bedrooms": 3,
            "bathrooms": 2,
            "guest_capacity": 6,
            "operating_mode": "year-round",
            "notes": "",
            "status": "ACTIVE",
        })

    def _seed_reservation(self, organization_id, reservation_id, property_id, property_name, guest_first_name, guest_last_name, arrival, departure):
        with app_module._owner_db_connection() as conn:
            app_module._ensure_owner_db_schema(conn)
            conn.execute(
                """
                INSERT INTO reservations (
                    id, created_at, updated_at, property_id, reservation_source, reservation_reference, channel_name,
                    channel_status, last_sync, external_payload, external_reference, external_last_sync, import_batch_id,
                    sync_status, source_metadata_json, guest_first_name, guest_last_name, guest_email, guest_phone,
                    adults, children, infants, pets, arrival_datetime, departure_datetime, status, notes, language,
                    created_by, metadata_json, organization_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reservation_id,
                    "2026-06-30T10:00:00+00:00",
                    "2026-06-30T10:00:00+00:00",
                    property_id,
                    "Manual",
                    reservation_id,
                    "Manual",
                    "SYNCED",
                    "",
                    "{}",
                    reservation_id,
                    "",
                    "",
                    "IDLE",
                    "{}",
                    guest_first_name,
                    guest_last_name,
                    f"{guest_first_name.lower()}@example.com",
                    "",
                    2,
                    0,
                    0,
                    0,
                    arrival,
                    departure,
                    "CONFIRMED",
                    "",
                    "en",
                    "workspace-test",
                    "{\"timeline\":[]}",
                    organization_id,
                ),
            )
        app_module._upsert_reservation_calendar_event(app_module._find_reservation(reservation_id))

    def _seed_task(self, organization_id, task_id, property_id, property_name, owner_id, owner_name, owner_email, status="NEW", due_date=""):
        app_module._upsert_operations_task({
            "id": task_id,
            "request_id": task_id,
            "source_type": "SERVICE_REQUEST",
            "source_id": task_id,
            "created_at": "2026-06-30T10:00:00+00:00",
            "updated_at": "2026-06-30T10:00:00+00:00",
            "title": f"Task {task_id}",
            "category": "Cleaning",
            "owner_name": owner_name,
            "owner_email": owner_email,
            "property_id": property_id,
            "property_name": property_name,
            "assigned_to": "",
            "assigned_professional_id": "",
            "priority": "HIGH",
            "status": status,
            "due_date": due_date,
            "notes": "",
            "completed_at": "",
            "owner_id": owner_id,
            "property_location": "Varna",
            "admin_notes": "",
            "request_status": "new",
            "organization_id": organization_id,
        })

    def _seed_calendar_event(self, organization_id, event_id, title):
        with app_module._owner_db_connection() as conn:
            app_module._ensure_owner_db_schema(conn)
            conn.execute(
                """
                INSERT INTO calendar_events (
                    id, created_at, updated_at, property_id, owner_id, operation_task_id, event_type, title, description,
                    start_datetime, end_datetime, all_day, status, assigned_professional, created_by, color, metadata_json,
                    organization_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    "2026-06-30T10:00:00+00:00",
                    "2026-06-30T10:00:00+00:00",
                    "",
                    "",
                    "",
                    "Other",
                    title,
                    "",
                    (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                    (datetime.now(timezone.utc) + timedelta(days=1, hours=1)).isoformat(),
                    0,
                    "SCHEDULED",
                    "",
                    "workspace-test",
                    "grey",
                    "{}",
                    organization_id,
                ),
            )

    def _seed_audit_log(self, organization_id, action, entity_id):
        with app.test_request_context("/workspace/audit"):
            app_module._append_audit_log(
                "workspace_test",
                entity_id,
                action,
                before={},
                after={"entity_id": entity_id},
                organization_id=organization_id,
                user_id="user-test",
                role_key=app_module.ROLE_COMPANY_ADMIN,
            )

    def test_company_admin_can_access_workspace_and_language_links_are_preserved(self):
        with patch.dict(os.environ, self._env(), clear=False):
            organization = app_module._upsert_organization({"name": "North Sea Rentals", "slug": "north-sea"})
            user = self._seed_workspace_user(organization, "admin@northsea.example", "Mila Petrova", app_module.ROLE_COMPANY_ADMIN)
            self._set_enterprise_session(user, organization, app_module.ROLE_COMPANY_ADMIN)

            response = self.client.get("/workspace/dashboard?lang=fr")
            html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('<html lang="fr">', html)
        self.assertIn("North Sea Rentals", html)
        self.assertIn(f'href="/workspace/properties?organization_id={organization["id"]}&amp;lang=fr"', html)
        self.assertIn(f'href="/workspace/users?organization_id={organization["id"]}&amp;lang=fr"', html)

    def test_manager_and_coordinator_have_limited_navigation(self):
        with patch.dict(os.environ, self._env(), clear=False):
            manager_org = app_module._upsert_organization({"name": "Manager Org", "slug": "manager-org"})
            manager_user = self._seed_workspace_user(manager_org, "manager@example.com", "Manager", app_module.ROLE_OPERATIONS_MANAGER)
            self._set_enterprise_session(manager_user, manager_org, app_module.ROLE_OPERATIONS_MANAGER)
            manager_html = self.client.get("/workspace/dashboard?lang=en").get_data(as_text=True)

            coordinator_org = app_module._upsert_organization({"name": "Coordinator Org", "slug": "coordinator-org"})
            coordinator_user = self._seed_workspace_user(coordinator_org, "coordinator@example.com", "Coordinator", app_module.ROLE_OPERATIONS_COORDINATOR)
            self._set_enterprise_session(coordinator_user, coordinator_org, app_module.ROLE_OPERATIONS_COORDINATOR)
            coordinator_html = self.client.get("/workspace/dashboard?lang=en").get_data(as_text=True)

        self.assertNotIn("Users", manager_html)
        self.assertNotIn("Invitations", manager_html)
        self.assertNotIn("Settings", manager_html)
        self.assertIn("Audit", manager_html)
        self.assertIn("Properties", coordinator_html)
        self.assertIn("Operations", coordinator_html)
        self.assertIn("Reservations", coordinator_html)
        self.assertIn("Calendar", coordinator_html)
        self.assertNotIn('href="/workspace/professionals', coordinator_html)
        self.assertNotIn("Audit", coordinator_html)

    def test_owner_and_professional_redirect_out_of_workspace(self):
        with patch.dict(os.environ, self._env(), clear=False):
            owner_org = app_module._upsert_organization({"name": "Owner Org", "slug": "owner-org"})
            owner_user = self._seed_workspace_user(owner_org, "owner@example.com", "Owner", app_module.ROLE_OWNER)
            self._set_enterprise_session(owner_user, owner_org, app_module.ROLE_OWNER)
            owner_response = self.client.get("/workspace/dashboard?lang=en")

            professional_org = app_module._upsert_organization({"name": "Pro Org", "slug": "pro-org"})
            professional_user = self._seed_workspace_user(professional_org, "pro@example.com", "Professional", app_module.ROLE_PROFESSIONAL)
            self._set_enterprise_session(professional_user, professional_org, app_module.ROLE_PROFESSIONAL)
            professional_response = self.client.get("/workspace/dashboard?lang=en")

        self.assertEqual(owner_response.status_code, 302)
        self.assertIn("/owners/dashboard", owner_response.headers["Location"])
        self.assertEqual(professional_response.status_code, 302)
        self.assertIn("/professionals/dashboard", professional_response.headers["Location"])

    def test_workspace_data_stays_scoped_to_organization(self):
        with patch.dict(os.environ, self._env(), clear=False):
            org_a = app_module._upsert_organization({"name": "Alpha Stay", "slug": "alpha-stay"})
            org_b = app_module._upsert_organization({"name": "Beta Stay", "slug": "beta-stay"})
            user_a = self._seed_workspace_user(org_a, "admin@alpha.example", "Alpha Admin", app_module.ROLE_COMPANY_ADMIN)
            self._seed_workspace_user(org_b, "admin@beta.example", "Beta Admin", app_module.ROLE_COMPANY_ADMIN)
            self._seed_owner_property(user_a["id"], "property-alpha", org_a["id"], "Alpha Villa", "Varna")
            self._seed_owner_property("owner-beta", "property-beta", org_b["id"], "Beta Villa", "Burgas")
            self._seed_reservation(org_a["id"], "reservation-alpha", "property-alpha", "Alpha Villa", "Anna", "Ivanova", "2026-07-03T10:00:00+00:00", "2026-07-06T10:00:00+00:00")
            self._seed_reservation(org_b["id"], "reservation-beta", "property-beta", "Beta Villa", "Boris", "Petrov", "2026-07-04T10:00:00+00:00", "2026-07-07T10:00:00+00:00")
            self._seed_task(org_a["id"], "task-alpha", "property-alpha", "Alpha Villa", user_a["id"], "Alpha Admin", "admin@alpha.example", due_date="2026-07-04")
            self._seed_task(org_b["id"], "task-beta", "property-beta", "Beta Villa", "owner-beta", "Beta Admin", "admin@beta.example", due_date="2026-07-05")
            self._seed_calendar_event(org_a["id"], "event-alpha", "Alpha event")
            self._seed_calendar_event(org_b["id"], "event-beta", "Beta event")
            self._seed_audit_log(org_a["id"], "created", "alpha-record")
            self._seed_audit_log(org_b["id"], "created", "beta-record")

            self._set_enterprise_session(user_a, org_a, app_module.ROLE_COMPANY_ADMIN)
            dashboard_html = self.client.get("/workspace/dashboard?lang=en").get_data(as_text=True)
            properties_html = self.client.get("/workspace/properties?lang=en").get_data(as_text=True)
            reservations_html = self.client.get("/workspace/reservations?lang=en").get_data(as_text=True)
            audit_html = self.client.get("/workspace/audit?lang=en").get_data(as_text=True)

        self.assertIn("Alpha event", dashboard_html)
        self.assertIn("alpha-record", audit_html)
        self.assertIn("Alpha Villa", properties_html)
        self.assertIn("anna@example.com", reservations_html)
        self.assertNotIn("Beta event", dashboard_html)
        self.assertNotIn("beta-record", audit_html)
        self.assertNotIn("Beta Villa", properties_html)
        self.assertNotIn("Boris Petrov", reservations_html)

    def test_workspace_invitation_flow_and_list(self):
        with patch.dict(os.environ, self._env(), clear=False):
            organization = app_module._upsert_organization({"name": "Invite Org", "slug": "invite-org"})
            user = self._seed_workspace_user(organization, "admin@invite.example", "Invite Admin", app_module.ROLE_COMPANY_ADMIN)
            self._set_enterprise_session(user, organization, app_module.ROLE_COMPANY_ADMIN)

            response = self.client.post(
                "/workspace/users?lang=en",
                data={
                    "workspace_action": "invite",
                    "email": "new.user@example.com",
                    "role": app_module.ROLE_OPERATIONS_MANAGER,
                },
            )
            invitations_html = self.client.get("/workspace/invitations?lang=en").get_data(as_text=True)

        self.assertEqual(response.status_code, 302)
        self.assertIn("new.user@example.com", invitations_html)
        self.assertIn(app_module.ROLE_OPERATIONS_MANAGER, invitations_html)

    def test_workspace_audit_and_settings_access(self):
        with patch.dict(os.environ, self._env(), clear=False):
            organization = app_module._upsert_organization({"name": "Audit Org", "slug": "audit-org", "metadata": {"legal_name": "Audit Legal", "region": "BG", "default_language": "en", "timezone": "Europe/Sofia"}})
            user = self._seed_workspace_user(organization, "admin@audit.example", "Audit Admin", app_module.ROLE_COMPANY_ADMIN)
            manager = self._seed_workspace_user(organization, "manager@audit.example", "Audit Manager", app_module.ROLE_OPERATIONS_MANAGER)
            self._seed_audit_log(organization["id"], "workspace_checked", "audit-1")
            self._set_enterprise_session(user, organization, app_module.ROLE_COMPANY_ADMIN)
            settings_html = self.client.get("/workspace/settings?lang=ru").get_data(as_text=True)
            audit_html = self.client.get("/workspace/audit?lang=ru").get_data(as_text=True)

            self._set_enterprise_session(manager, organization, app_module.ROLE_OPERATIONS_MANAGER)
            manager_settings = self.client.get("/workspace/settings?lang=ru")

        self.assertEqual(manager_settings.status_code, 403)
        self.assertIn("Audit Legal", settings_html)
        self.assertIn("workspace_checked", audit_html)
        self.assertIn('<html lang="ru">', settings_html)

    def test_workspace_platform_admin_must_select_organization(self):
        with unittest.mock.patch.dict(os.environ, self._env(), clear=False):
            organization = app_module._upsert_organization({"name": "Select Org", "slug": "select-org"})
            user = app_module._upsert_user({
                "email": "platform@example.com",
                "full_name": "Platform Admin",
                "organization_id": organization["id"],
                "status": "ACTIVE",
            })
            app_module._upsert_membership({
                "user_id": user["id"],
                "organization_id": organization["id"],
                "role_key": app_module.ROLE_PLATFORM_ADMIN,
                "status": "ACTIVE",
            })
            self._set_enterprise_session(user, organization, app_module.ROLE_PLATFORM_ADMIN)
            root_html = self.client.get("/workspace?lang=en").get_data(as_text=True)

        self.assertIn("Choose an organization", root_html)
        self.assertIn("Select Org", root_html)


if __name__ == "__main__":
    unittest.main()


