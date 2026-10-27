import tempfile
import unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from cacl_ca.workbook import read_workbook, normalize_header, extract_ca
from tests.support import source_path


class WorkbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = read_workbook(source_path())

    def test_extracts_ca_without_summaries_as_trades(self):
        snapshot = extract_ca(self.book)
        self.assertEqual(len(snapshot["trades"]), 125)
        self.assertEqual(len(snapshot["cashflows"]), 45)
        self.assertEqual(len(snapshot["symbols"]), 72)
        self.assertEqual({p["symbol"]: Decimal(p["quantity"]) for p in snapshot["positions"]
                          if p["included"]}, {"SPY": Decimal(134), "LLY": Decimal(51)})
        self.assertEqual(snapshot["as_of"], "2026-10-27")
        self.assertEqual(sum(Decimal(f["amount"]) for f in snapshot["cashflows"])
                         .quantize(Decimal("0.01")), Decimal("1833.60"))
        self.assertFalse([i for i in snapshot["issues"] if i["severity"] == "error"])
        self.assertEqual(snapshot["balances"]["nominal_capital"], "1000000")
        self.assertEqual(len(snapshot["adjustments"]), 2)
        self.assertEqual(len(snapshot["history"]), 261)

    def test_missing_quantity_blocks_the_snapshot(self):
        book = deepcopy(self.book)
        book["sheets"]["Cartera_CA"]["cells"]["D5"]["value"] = None
        snapshot = extract_ca(book)
        self.assertTrue(any(i["severity"] == "error" for i in snapshot["issues"]))

    def test_missing_required_headers_are_clear_errors(self):
        for sheet, address in (("Cartera_CA", "G4"), ("Liquidación_Posiciones_CA", "G2")):
            with self.subTest(sheet=sheet):
                book = deepcopy(self.book)
                del book["sheets"][sheet]["cells"][address]
                with self.assertRaisesRegex(ValueError, "encabezado"):
                    extract_ca(book)

    def test_rows_with_money_but_missing_identifiers_are_not_silently_skipped(self):
        for sheet, addresses in (("Cartera_CA", ("C5", "D5")),
                                  ("Liquidación_Posiciones_CA", ("C4", "K4"))):
            with self.subTest(sheet=sheet):
                book = deepcopy(self.book)
                for address in addresses:
                    del book["sheets"][sheet]["cells"][address]
                self.assertTrue(any(i["severity"] == "error" for i in extract_ca(book)["issues"]))

    def test_excel_error_in_symbol_blocks_the_snapshot(self):
        book = deepcopy(self.book)
        book["sheets"]["Cartera_CA"]["cells"]["C5"].update(value="#VALUE!", kind="error")
        self.assertTrue(any(i["severity"] == "error" for i in extract_ca(book)["issues"]))

    def test_dividend_rows_can_move(self):
        from openpyxl.utils.cell import coordinate_from_string
        book = deepcopy(self.book)
        cells = book["sheets"]["Dividend Payments"]["cells"]
        shifted = {}
        for address, cell in cells.items():
            column, row = coordinate_from_string(address)
            shifted[f"{column}{row+3}"] = cell
        book["sheets"]["Dividend Payments"]["cells"] = shifted
        snapshot = extract_ca(book)
        self.assertEqual(len(snapshot["cashflows"]), 45)
        self.assertEqual(Decimal(snapshot["balances"]["reported_cashflows"])
                         .quantize(Decimal("0.01")), Decimal("1833.60"))

    def test_unknown_right_block_is_not_lost(self):
        book = deepcopy(self.book)
        book["sheets"]["History_CA"]["cells"]["AZ2"] = {
            "value": "New metric", "formula": None, "kind": "text", "number_format": "General"}
        snapshot = extract_ca(book)
        self.assertIn("AZ2", snapshot["source_cells"]["History_CA"])
        self.assertTrue(any(i["code"] == "unknown_block" for i in snapshot["issues"]))

    def test_closed_trade_outside_table_is_flagged(self):
        book = deepcopy(self.book)
        book["sheets"]["Liquidación_Posiciones_CA"]["tables"]["Trades"] = "A2:N127"
        snapshot = extract_ca(book)
        self.assertTrue(any(i["code"] == "table_range_incomplete" and i["severity"] == "error"
                            for i in snapshot["issues"]))

    def test_missing_balance_is_not_zero(self):
        book = deepcopy(self.book)
        del book["sheets"]["Cartera_CA"]["cells"]["H15"]
        snapshot = extract_ca(book)
        self.assertIsNone(snapshot["balances"]["cash"])
        self.assertTrue(any(i["severity"] == "error" for i in snapshot["issues"]))

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
