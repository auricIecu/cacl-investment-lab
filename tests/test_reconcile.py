import unittest
from copy import deepcopy
from decimal import Decimal

from cacl_ca.workbook import read_workbook, extract_ca
from cacl_ca.reconcile import reconcile
from tests.support import source_path


class ReconcileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = extract_ca(read_workbook(source_path()))

    def test_reconciles_real_money_and_preserves_findings(self):
        report = reconcile(self.snapshot)
        expected = {"trade_pnl": "-128407.33", "adjusted_pnl": "-128422.52",
                    "cashflow_total": "1833.60", "positions_value": "168508.86",
                    "cash": "809190.11", "equity": "977698.97"}
        for name, amount in expected.items():
            self.assertEqual(Decimal(report["metrics"][name]).quantize(Decimal("0.01")), Decimal(amount))
        self.assertEqual(report["metrics"]["closed_rows"], 125)
        self.assertEqual(report["metrics"]["wins"], 78)
        self.assertEqual(report["metrics"]["losses"], 46)
        self.assertEqual(report["metrics"]["flat"], 1)
        self.assertEqual(report["metrics"]["win_rate"], "0.624")
        self.assertTrue(all(c["passed"] for c in report["checks"]), report["checks"])
        codes = {i["code"] for i in report["issues"]}
        self.assertTrue({"stale_summary_range", "chart_series_incomplete", "summary_count_label_mismatch",
                         "return_basis_mismatch", "instrument_eligibility_unverified"} <= codes)
        self.assertEqual(report["status"], "review_required")
        self.assertGreater(len(report["reference_metrics"]), 40)
        self.assertEqual({s["name"] for s in report["series"]}, {"daily", "weekly", "monthly", "chart"})

    def test_wrong_equity_is_invalid(self):
        snapshot = deepcopy(self.snapshot)
        snapshot["balances"]["equity"] = "977700.00"
        report = reconcile(snapshot)
        self.assertEqual(report["status"], "invalid")
        self.assertTrue(any(not c["passed"] for c in report["checks"]))

    def test_missing_money_does_not_crash_or_become_zero(self):
        snapshot = deepcopy(self.snapshot)
        snapshot["positions"][0]["quantity"] = None
        report = reconcile(snapshot)
        self.assertEqual(report["status"], "invalid")
        self.assertIsNone(report["metrics"]["positions_value"])

    def test_negative_withholding_changes_cashflow_total(self):
        snapshot = deepcopy(self.snapshot)
        snapshot["cashflows"][0]["amount"] = "16.7"
        report = reconcile(snapshot)
        self.assertEqual(report["status"], "invalid")
        self.assertEqual(Decimal(report["metrics"]["cashflow_total"]).quantize(Decimal("0.01")),
                         Decimal("1867.00"))

    def test_zero_loss_does_not_create_infinite_ratio(self):
        snapshot = deepcopy(self.snapshot)
        snapshot["trades"] = [t for t in snapshot["trades"] if Decimal(t["pnl"]) >= 0]
        report = reconcile(snapshot)
        self.assertIsNone(report["metrics"]["profit_factor"])
        self.assertIn("undefined_profit_factor", {i["code"] for i in report["issues"]})

    def test_order_of_trades_does_not_change_metrics(self):
        snapshot = deepcopy(self.snapshot)
        snapshot["trades"].reverse()
        self.assertEqual(reconcile(snapshot)["metrics"], reconcile(self.snapshot)["metrics"])

    def test_duplicate_adjustment_is_detected(self):
        snapshot = deepcopy(self.snapshot)
        snapshot["adjustments"].append(snapshot["adjustments"][0])
        self.assertEqual(reconcile(snapshot)["status"], "invalid")

    def test_restored_range_removes_stale_summary_warning(self):
        snapshot = deepcopy(self.snapshot)
        cells = snapshot["source_cells"]["History_CA"]
        for cell in cells.values():
            if cell["formula"]:
                cell["formula"] = cell["formula"].replace("$266", "$271")
        report = reconcile(snapshot)
        self.assertNotIn("stale_summary_range", {i["code"] for i in report["issues"]})
