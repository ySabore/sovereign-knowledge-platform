from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services.billing import (
    DEFAULT_PLAN_PRICE_DISPLAY,
    apply_subscription_object_to_org,
    create_checkout_session,
    get_plan_entitlements,
    handle_checkout_session_completed,
    list_invoice_history,
    list_plan_catalog,
    normalize_plan_key,
)


class BillingEntitlementsTests(unittest.TestCase):
    class _FakeDb:
        def __init__(self, org: SimpleNamespace) -> None:
            self.org = org
            self.committed = False
            self.added: list[object] = []

        def get(self, model, object_id):
            _ = model
            return self.org if object_id == self.org.id else None

        def add(self, value: object) -> None:
            self.added.append(value)

        def commit(self) -> None:
            self.committed = True

    def test_normalize_unknown_plan_maps_to_free(self) -> None:
        self.assertEqual(normalize_plan_key("unknown-xyz"), "free")

    def test_free_trial_maps_to_free_bucket(self) -> None:
        self.assertEqual(normalize_plan_key("free_trial"), "free")

    def test_starter_entitlements(self) -> None:
        ent = get_plan_entitlements("starter")
        self.assertEqual(ent.seats, 3)
        self.assertEqual(ent.connectors, 2)
        self.assertGreater(ent.queries_per_month, 0)

    def test_plan_catalog_has_expected_keys(self) -> None:
        catalog = list_plan_catalog()
        self.assertGreaterEqual(len(catalog), 5)
        plans = {row["plan"] for row in catalog}
        self.assertIn("free", plans)
        self.assertIn("business", plans)
        first = catalog[0]
        self.assertIn("price_id", first)
        self.assertIn("queries_per_month", first)
        self.assertIn("queries_per_day", first)
        self.assertIn("queries_per_hour", first)
        self.assertIn("price_display", first)

    def test_default_price_display_labels_present(self) -> None:
        self.assertIn("starter", DEFAULT_PLAN_PRICE_DISPLAY)
        self.assertTrue(DEFAULT_PLAN_PRICE_DISPLAY["free"].startswith("$0"))

    def test_plan_catalog_includes_default_price_display_when_env_empty(self) -> None:
        catalog = list_plan_catalog()
        by_plan = {row["plan"]: row.get("price_display") for row in catalog}
        self.assertEqual(by_plan.get("free"), "$0")
        self.assertIsInstance(by_plan.get("business"), str)
        self.assertGreater(len(str(by_plan.get("business"))), 3)

    def test_list_invoice_history_returns_empty_for_missing_customer(self) -> None:
        class FakeInvoice:
            @staticmethod
            def list(*args, **kwargs):
                raise RuntimeError("Request req_123: No such customer: 'cus_seed_demo'")

        fake_stripe = SimpleNamespace(Invoice=FakeInvoice)
        org = SimpleNamespace(id="org-1", stripe_customer_id="cus_seed_demo")

        with patch("app.services.billing.stripe_configured", return_value=True), patch(
            "app.services.billing._configure_stripe"
        ), patch.dict(sys.modules, {"stripe": fake_stripe}):
            rows = list_invoice_history(org=org, limit=20)
        self.assertEqual(rows, [])

    def test_create_checkout_session_blocks_when_subscription_already_active(self) -> None:
        class FakeSub:
            @staticmethod
            def retrieve(sub_id: str):
                if sub_id != "sub_active_demo":
                    raise AssertionError(f"unexpected subscription id: {sub_id}")
                return {"id": sub_id, "status": "active"}

        fake_stripe = SimpleNamespace(Subscription=FakeSub)
        org = SimpleNamespace(
            id="org-1",
            stripe_subscription_id="sub_active_demo",
            stripe_customer_id="cus_demo",
        )

        with patch("app.services.billing.stripe_configured", return_value=True), patch(
            "app.services.billing._configure_stripe"
        ), patch.dict(sys.modules, {"stripe": fake_stripe}):
            with self.assertRaises(RuntimeError) as ctx:
                create_checkout_session(
                    db=None,  # type: ignore[arg-type]
                    org=org,  # type: ignore[arg-type]
                    price_id="price_new",
                    success_url="http://localhost/success",
                    cancel_url="http://localhost/cancel",
                )
        self.assertIn("already has an active Stripe subscription", str(ctx.exception))

    def test_incomplete_subscription_does_not_grant_paid_entitlements(self) -> None:
        org = SimpleNamespace(
            id=uuid4(),
            plan="free",
            stripe_subscription_id=None,
            stripe_customer_id=None,
        )
        subscription = {
            "id": "sub_pending",
            "customer": "cus_pending",
            "status": "incomplete",
            "items": {"data": [{"price": {"id": "price_business"}}]},
        }

        with patch("app.services.billing.price_id_to_plan", return_value="business"), patch(
            "app.services.billing.invalidate_plan_cache"
        ):
            apply_subscription_object_to_org(None, org, subscription)  # type: ignore[arg-type]

        self.assertEqual(org.plan, "free")
        self.assertEqual(org.stripe_subscription_id, "sub_pending")
        self.assertEqual(org.stripe_customer_id, "cus_pending")

    def test_unpaid_checkout_keeps_plan_free_without_retrieving_subscription(self) -> None:
        org = SimpleNamespace(
            id=uuid4(),
            plan="free",
            stripe_subscription_id=None,
            stripe_customer_id=None,
        )
        db = self._FakeDb(org)
        session = {
            "id": "cs_pending",
            "customer": "cus_pending",
            "subscription": "sub_pending",
            "payment_status": "unpaid",
            "metadata": {"organization_id": str(org.id)},
        }

        with patch("app.services.billing.stripe_configured", return_value=True), patch(
            "app.services.billing.invalidate_plan_cache"
        ), patch("app.services.billing._configure_stripe") as configure:
            handle_checkout_session_completed(db, session)  # type: ignore[arg-type]

        configure.assert_not_called()
        self.assertEqual(org.plan, "free")
        self.assertEqual(org.stripe_subscription_id, "sub_pending")
        self.assertEqual(org.stripe_customer_id, "cus_pending")
        self.assertTrue(db.committed)

    def test_paid_checkout_grants_active_subscription_plan(self) -> None:
        class FakeSub:
            @staticmethod
            def retrieve(sub_id: str):
                return {
                    "id": sub_id,
                    "customer": "cus_paid",
                    "status": "active",
                    "items": {"data": [{"price": {"id": "price_business"}}]},
                }

        fake_stripe = SimpleNamespace(Subscription=FakeSub)
        org = SimpleNamespace(
            id=uuid4(),
            plan="free",
            stripe_subscription_id=None,
            stripe_customer_id=None,
        )
        db = self._FakeDb(org)
        session = {
            "id": "cs_paid",
            "customer": "cus_paid",
            "subscription": "sub_paid",
            "payment_status": "paid",
            "metadata": {"organization_id": str(org.id)},
        }

        with patch("app.services.billing.stripe_configured", return_value=True), patch(
            "app.services.billing._configure_stripe"
        ), patch("app.services.billing.price_id_to_plan", return_value="business"), patch(
            "app.services.billing.invalidate_plan_cache"
        ), patch.dict(sys.modules, {"stripe": fake_stripe}):
            handle_checkout_session_completed(db, session)  # type: ignore[arg-type]

        self.assertEqual(org.plan, "business")
        self.assertEqual(org.stripe_subscription_id, "sub_paid")
        self.assertTrue(db.committed)


if __name__ == "__main__":
    unittest.main()
