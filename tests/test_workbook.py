import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from cacl_ca.workbook import read_workbook, normalize_header
from tests.support import source_path


class WorkbookTests(unittest.TestCase):
    def test_reads_right_panels_and_only_ca_dividends(self):
        book = read_workbook(source_path())
        self.assertIn("AJ10", book["sheets"]["History_CA"]["cells"])
        self.assertIn("Z55", book["sheets"]["Liquidación_Posiciones_CA"]["cells"])
        self.assertIn("G50", book["sheets"]["Dividend Payments"]["cells"])
        self.assertNotIn("G56", book["sheets"]["Dividend Payments"]["cells"])
        self.assertNotIn("G88", book["sheets"]["Dividend Payments"]["cells"])
        self.assertNotIn("Cartera_CL", book["sheets"])
        self.assertIn("$AH$266", book["sheets"]["History_CA"]["cells"]["AH3"]["formula"])
        self.assertEqual(book["sheets"]["Liquidación_Posiciones_CA"]["tables"]["Trades"], "A2:N128")

    def test_normalizes_excel_spaces(self):
        self.assertEqual(normalize_header("Invested\u00a0"), "invested")

    def test_preserves_excel_error_as_error(self):
        book = read_workbook(source_path())
        cell = book["sheets"]["Cartera_CA"]["cells"]["B5"]
        self.assertEqual(cell["kind"], "error")
        self.assertEqual(cell["value"], "#VALUE!")

    def test_missing_cache_is_preserved_and_no_fixed_column_cutoff(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.xlsx"
            wb = Workbook()
            wb.remove(wb.active)
            for name in ("Cartera_CA", "Liquidación_Posiciones_CA", "History_CA",
                         "Dividend Payments", "Risk_Management"):
                wb.create_sheet(name)
            wb["Dividend Payments"]["C2"] = "Dividend Payments_CA"
            wb["Dividend Payments"]["C8"] = "Dividend Payments_CL"
            wb["History_CA"]["AZ99"] = "=1+1"
            wb.save(path)
            wb.close()
            cell = read_workbook(path)["sheets"]["History_CA"]["cells"]["AZ99"]
            self.assertEqual(cell["formula"], "=1+1")
            self.assertIsNone(cell["value"])

    def test_rejects_missing_required_sheets(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.xlsx"
            Workbook().save(path)
            with self.assertRaisesRegex(ValueError, "hoja"):
                read_workbook(path)
