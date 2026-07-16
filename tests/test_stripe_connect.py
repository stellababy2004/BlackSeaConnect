import base64
import gc
import os
import shutil
import sqlite3
import unittest
import uuid
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module
from app import app


class FormNestingAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.nested = False

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            self.nested = self.nested or self.depth > 0
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == "form" and self.depth:
            self.depth -= 1


class StripeConnectTests(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmpdir = Path(self.cwd) / f".tmp_stripe_tests_{uuid.uuid4().hex}"
        self.tmpdir.mkdir()
        os.chdir(self.tmpdir)
        self.db_path = self.tmpdir / "stripe.db"
        self.env = {
            "OWNER_DB_PATH": str(self.db_path), "ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "secret",
            "STRIPE_CONNECT_ENABLED": "1", "STRIPE_MODE": "test", "STRIPE_SECRET_KEY": "test-secret-placeholder",
            "STRIPE_PUBLISHABLE_KEY": "test-publishable-placeholder", "STRIPE_WEBHOOK_SECRET": "test-webhook-placeholder", "SITE_URL": "https://example.test",
        }
        self.env_patcher = patch.dict(os.environ, self.env, clear=False)
        self.env_patcher.start()
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.owner = None
        self.professional = None

    def tearDown(self):
        self.env_patcher.stop()
        os.chdir(self.cwd)
        self.client = None
        gc.collect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def auth(self):
        value = base64.b64encode(b"admin:secret").decode("ascii")
        return {"Authorization": f"Basic {value}"}

    def seed(self, task_id="stripe-task", *, quote_status="APPROVED", payment_status="PENDING", payout_status="NOT_READY", provider=""):
        with patch.dict(os.environ, self.env, clear=True):
            self.owner = app_module._upsert_owner_account({
                "id": "owner-stripe", "created_at": app_module._utc_now_iso(), "full_name": "Stripe Owner",
                "email": "owner@example.com", "phone": "+3591", "status": "ACTIVE",
            })
            app_module._append_owner_property({
                "id": "property-1", "owner_id": self.owner["id"], "created_at": app_module._utc_now_iso(),
                "name": "Stripe Villa", "property_type": "villa", "location": "Varna", "status": "ACTIVE",
            })
            self.professional = app_module._upsert_professional_account({
                "id": "pro-stripe", "created_at": app_module._utc_now_iso(), "full_name": "Stripe Pro",
                "email": "pro@example.com", "phone": "+3592", "status": "ACTIVE",
            })
            app_module._upsert_operations_task_from_source({
                "id": task_id, "request_id": task_id, "source_id": task_id, "source_type": "OWNER_SERVICE_REQUEST",
                "title": "Secure repair", "owner_id": self.owner["id"], "owner_email": self.owner["email"],
                "assigned_professional_id": self.professional["id"], "property_id": "property-1", "status": "NEW",
            }, force_create=True, notify=False)
            with app_module._owner_db_connection() as conn:
                conn.execute("""UPDATE operations_tasks SET professional_quote_amount=100, platform_fee_value=20,
                    owner_total_amount=120, currency='EUR', quote_status=?, owner_approval_status='APPROVED',
                    payment_status=?, payout_status=?, payment_provider=?, quote_locked=1 WHERE id=?""",
                    (quote_status, payment_status, payout_status, provider, task_id))
        return app_module._find_operations_task(task_id)

    def owner_session(self, owner=None):
        owner = owner or self.owner
        with self.client.session_transaction() as session_data:
            session_data[app_module.OWNER_SESSION_LOGGED_IN_KEY] = True
            session_data[app_module.OWNER_SESSION_ID_KEY] = owner["id"]
            session_data[app_module.OWNER_SESSION_EMAIL_KEY] = owner["email"]
            session_data["_owner_finance_csrf_token"] = "owner-csrf"

    def test_missing_configuration_fails_closed_without_secrets_in_diagnostics(self):
        with patch.dict(os.environ, {"STRIPE_CONNECT_ENABLED": "1"}, clear=True):
            self.assertFalse(app_module._stripe_configured())
            diagnostics = app_module._stripe_admin_diagnostics()
            self.assertFalse(diagnostics["checkout_ready"])
            self.assertNotIn("secret_key", diagnostics)
            self.assertNotIn("webhook_secret", diagnostics)

    def test_professional_onboarding_creates_once_and_reuses_stored_account(self):
        self.seed()
        with self.client.session_transaction() as session_data:
            session_data[app_module.PROFESSIONAL_SESSION_LOGGED_IN_KEY] = True
            session_data[app_module.PROFESSIONAL_SESSION_ID_KEY] = self.professional["id"]
            session_data[app_module.PROFESSIONAL_SESSION_EMAIL_KEY] = self.professional["email"]
            session_data["_professional_stripe_csrf_token"] = "pro-csrf"
        account = SimpleNamespace(id="acct_created")
        link = SimpleNamespace(url="https://connect.stripe.test/onboarding")
        with patch.object(app_module.stripe.Account, "create", return_value=account) as create, patch.object(app_module.stripe.AccountLink, "create", return_value=link) as create_link:
            first = self.client.post("/professionals/stripe/connect", data={"csrf_token": "pro-csrf", "stripe_account_id": "acct_attacker"})
            second = self.client.post("/professionals/stripe/connect", data={"csrf_token": "pro-csrf", "stripe_account_id": "acct_attacker_2"})
        self.assertEqual(first.status_code, 303)
        self.assertEqual(second.status_code, 303)
        self.assertEqual(create.call_count, 1)
        self.assertEqual(create_link.call_count, 2)
        self.assertEqual(app_module._find_professional_account("pro-stripe")["stripe_account_id"], "acct_created")

    def test_checkout_uses_server_amount_and_owner_scope_without_marking_paid(self):
        self.seed()
        self.owner_session()
        missing_csrf = self.client.post("/owners/finance/stripe-task/stripe-checkout", data={})
        self.assertEqual(missing_csrf.status_code, 403)
        page = self.client.get("/owners/dashboard?lang=en")
        audit = FormNestingAudit()
        audit.feed(page.get_data(as_text=True))
        self.assertFalse(audit.nested)
        self.assertIn("Pay securely with Stripe", page.get_data(as_text=True))
        checkout = SimpleNamespace(id="cs_test_1", url="https://checkout.stripe.test/session")
        with patch.dict(os.environ, self.env, clear=True), patch.object(app_module.stripe.checkout.Session, "create", return_value=checkout) as create:
            response = self.client.post("/owners/finance/stripe-task/stripe-checkout", data={
                "csrf_token": "owner-csrf", "amount": "1", "currency": "JPY", "professional_id": "attacker",
            })
        self.assertEqual(response.status_code, 303)
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["line_items"][0]["price_data"]["unit_amount"], 12000)
        self.assertEqual(kwargs["line_items"][0]["price_data"]["currency"], "eur")
        self.assertEqual(kwargs["metadata"]["professional_id"], "pro-stripe")
        task = app_module._find_operations_task("stripe-task")
        self.assertEqual(task["payment_status"], "PENDING")
        self.assertEqual(task["stripe_payment_status"], "CHECKOUT_OPEN")

        with patch.dict(os.environ, self.env, clear=True):
            other = app_module._upsert_owner_account({"id": "other", "created_at": app_module._utc_now_iso(), "full_name": "Other", "email": "other@example.com", "phone": "1", "status": "ACTIVE"})
        self.owner_session(other)
        denied = self.client.post("/owners/finance/stripe-task/stripe-checkout", data={"csrf_token": "owner-csrf"})
        self.assertEqual(denied.status_code, 404)

    def checkout_event(self, event_id="evt_paid", *, amount=12000, currency="eur", event_type="checkout.session.completed"):
        task = app_module._find_operations_task("stripe-task")
        return {"id": event_id, "type": event_type, "data": {"object": {
            "id": task["stripe_checkout_session_id"], "client_reference_id": task["id"], "payment_intent": "pi_test_1",
            "amount_total": amount, "currency": currency, "payment_status": "paid",
            "metadata": {"task_id": task["id"], "owner_id": task["owner_id"], "property_id": task["property_id"],
                         "professional_id": task["assigned_professional_id"], "finance_reference": task["finance_reference"]},
        }}}

    def prepare_checkout(self):
        self.seed()
        self.owner_session()
        checkout = SimpleNamespace(id="cs_test_1", url="https://checkout.stripe.test/session")
        with patch.dict(os.environ, self.env, clear=True), patch.object(app_module.stripe.checkout.Session, "create", return_value=checkout):
            self.client.post("/owners/finance/stripe-task/stripe-checkout", data={"csrf_token": "owner-csrf"})

    def post_event(self, event):
        with patch.dict(os.environ, self.env, clear=True), patch.object(app_module.stripe.Webhook, "construct_event", return_value=event):
            return self.client.post("/webhooks/stripe", data=b"{}", headers={"Stripe-Signature": "mock-signature"})

    def test_signed_webhook_reconciles_payment_and_duplicate_is_idempotent(self):
        self.prepare_checkout()
        event = self.checkout_event()
        self.assertEqual(self.post_event(event).status_code, 200)
        task = app_module._find_operations_task("stripe-task")
        self.assertEqual((task["quote_status"], task["payment_status"], task["payout_status"], task["payment_provider"]), ("FUNDED", "PAID", "READY", "STRIPE"))
        self.assertEqual(self.post_event(event).get_json()["duplicate"], True)
        events = [row for row in app_module._load_operations_task_events("stripe-task") if row["event_type"] == "stripe_payment_confirmed"]
        self.assertEqual(len(events), 1)

    def test_invalid_signature_and_reconciliation_mismatch_never_mark_paid(self):
        self.prepare_checkout()
        with patch.dict(os.environ, self.env, clear=True), patch.object(app_module.stripe.Webhook, "construct_event", side_effect=ValueError("bad")):
            invalid = self.client.post("/webhooks/stripe", data=b"{}", headers={"Stripe-Signature": "bad"})
        self.assertEqual(invalid.status_code, 400)
        mismatch = self.post_event(self.checkout_event("evt_mismatch", amount=1, currency="jpy"))
        self.assertEqual(mismatch.status_code, 200)
        self.assertEqual(app_module._find_operations_task("stripe-task")["payment_status"], "PENDING")
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT processing_status FROM stripe_event_ledger WHERE event_id='evt_mismatch'").fetchone()[0], "REJECTED")

    def test_failed_payment_stays_unpaid_and_account_update_syncs_readiness(self):
        self.prepare_checkout()
        failed = self.checkout_event("evt_failed", event_type="checkout.session.async_payment_failed")
        self.assertEqual(self.post_event(failed).status_code, 200)
        task = app_module._find_operations_task("stripe-task")
        self.assertEqual(task["payment_status"], "PENDING")
        self.assertEqual(task["stripe_payment_status"], "FAILED")

        with app_module._owner_db_connection() as conn:
            conn.execute("UPDATE professional_accounts SET stripe_account_id='acct_ready', stripe_account_status='INCOMPLETE' WHERE id='pro-stripe'")
        account_event = {"id": "evt_account", "type": "account.updated", "data": {"object": {
            "id": "acct_ready", "details_submitted": True, "charges_enabled": True, "payouts_enabled": True, "requirements": {},
        }}}
        self.assertEqual(self.post_event(account_event).status_code, 200)
        professional = app_module._find_professional_account("pro-stripe")
        self.assertEqual(professional["stripe_account_status"], "READY")
        self.assertTrue(professional["stripe_payouts_enabled"])

    def test_account_update_transfer_amount_idempotency_and_refund_freeze(self):
        task = self.seed(quote_status="FUNDED", payment_status="PAID", payout_status="READY", provider="STRIPE")
        with patch.dict(os.environ, self.env, clear=True), app_module._owner_db_connection() as conn:
            conn.execute("UPDATE operations_tasks SET finance_reference='FIN-stable', stripe_payment_intent_id='pi_test_1' WHERE id='stripe-task'")
            conn.execute("UPDATE professional_accounts SET stripe_account_id='acct_1', stripe_account_status='READY', stripe_details_submitted=1, stripe_charges_enabled=1, stripe_payouts_enabled=1 WHERE id='pro-stripe'")
        transfer = SimpleNamespace(id="tr_test_1")
        with patch.dict(os.environ, self.env, clear=True), patch.object(app_module.stripe.Transfer, "create", return_value=transfer) as create:
            paid_out, error = app_module._stripe_transfer_for_task(app_module._find_operations_task("stripe-task"))
            again, second_error = app_module._stripe_transfer_for_task(app_module._find_operations_task("stripe-task"))
        self.assertIsNone(error)
        self.assertEqual(paid_out["payout_status"], "PAID")
        self.assertEqual(create.call_args.kwargs["amount"], 10000)
        self.assertEqual(create.call_args.kwargs["idempotency_key"], "transfer-stripe-task-FIN-stable")
        self.assertEqual(create.call_count, 1)
        self.assertEqual(second_error, "invalid_payout_state")

        dispute = {"id": "evt_dispute", "type": "charge.dispute.created", "data": {"object": {"payment_intent": "pi_test_1"}}}
        self.post_event(dispute)
        self.assertEqual(app_module._find_operations_task("stripe-task")["payout_status"], "REQUIRES_REVIEW")

    def test_no_transfer_without_ready_account_and_localized_pages_render(self):
        self.seed(quote_status="FUNDED", payment_status="PAID", payout_status="READY", provider="STRIPE")
        with patch.dict(os.environ, self.env, clear=True), app_module._owner_db_connection() as conn:
            conn.execute("UPDATE operations_tasks SET finance_reference='FIN-stable' WHERE id='stripe-task'")
        with patch.dict(os.environ, self.env, clear=True), patch.object(app_module.stripe.Transfer, "create") as create:
            result, error = app_module._stripe_transfer_for_task(app_module._find_operations_task("stripe-task"))
        self.assertIsNone(result)
        self.assertEqual(error, "professional_not_ready")
        create.assert_not_called()
        self.owner_session()
        for lang in ("bg", "en", "fr"):
            with patch.dict(os.environ, self.env, clear=True):
                self.assertEqual(self.client.get(f"/owners/dashboard?lang={lang}").status_code, 200)

    def test_refund_before_transfer_freezes_payout(self):
        self.seed(quote_status="FUNDED", payment_status="PAID", payout_status="READY", provider="STRIPE")
        with app_module._owner_db_connection() as conn:
            conn.execute("UPDATE operations_tasks SET stripe_payment_intent_id='pi_refund' WHERE id='stripe-task'")
        refund = {"id": "evt_refund", "type": "charge.refunded", "data": {"object": {"payment_intent": "pi_refund", "refunded": True}}}
        self.assertEqual(self.post_event(refund).status_code, 200)
        task = app_module._find_operations_task("stripe-task")
        self.assertEqual(task["payment_status"], "REFUNDED")
        self.assertEqual(task["payout_status"], "PAYOUT_FROZEN")


if __name__ == "__main__":
    unittest.main()
