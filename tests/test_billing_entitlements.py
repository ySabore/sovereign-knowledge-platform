from __future__ import annotations

import unittest

from app.services.billing import get_plan_entitlements, normalize_plan_key


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


if __name__ == "__main__":
    unittest.main()
