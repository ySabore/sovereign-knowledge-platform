from __future__ import annotations

import unittest

from app.services.billing import DEFAULT_PLAN_PRICE_DISPLAY, get_plan_entitlements, list_plan_catalog, normalize_plan_key


class BillingEntitlementsTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
