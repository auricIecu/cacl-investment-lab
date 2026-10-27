import sqlite3
from contextlib import closing
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from tests.support import source_path


def change_cached_cell(source, destination, sheet_file, address, value):
    """Change an Excel cached value without destroying other formula caches."""
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, "w") as output:
        for entry in original.infolist():
            data = original.read(entry.filename)
            if entry.filename == sheet_file:
                root = ET.fromstring(data)
                cell = root.find(f'.//s:c[@r="{address}"]/s:v', ns)
                if cell is None:
                    raise AssertionError(f"Missing test cell {address}")
                cell.text = value
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            output.writestr(entry, data)


class CliTests(unittest.TestCase):
    def run_import(self, source, output):
        return subprocess.run([sys.executable, "-m", "cacl_ca", "import", str(source),
                               "--output-dir", str(output)], capture_output=True, text=True)

    def test_import_twice_preserves_original_and_report_and_one_revision(self):
        before = source_path().read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            result = self.run_import(source_path(), output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("review_required", result.stdout)
            report = next((output / "reports").glob("*.md"))
            text = report.read_text()
            self.assertIn("977,698.97", text)
            self.assertIn("stale_summary_range", text)
            self.assertIn("Dividend Payments", text)
            self.assertNotIn("4,577.49", text)
            again = self.run_import(source_path(), output)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual(report.read_text(), text)
            with closing(sqlite3.connect(output / "ca.sqlite3")) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM imports").fetchone()[0], 1)
        self.assertEqual(source_path().read_bytes(), before)

    def test_missing_file_exits_one_without_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_import(Path(folder) / "absent.xlsx", Path(folder) / "output")
            self.assertEqual(result.returncode, 1)
            self.assertIn("Error:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((Path(folder) / "output" / "ca.sqlite3").exists())

    def test_invalid_equity_exits_two_and_does_not_persist_portfolio(self):
        with tempfile.TemporaryDirectory() as folder:
            altered = Path(folder) / "altered.xlsx"
            change_cached_cell(source_path(), altered, "xl/worksheets/sheet5.xml", "H20", "1")
            output = Path(folder) / "output"
            result = self.run_import(altered, output)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("invalid", result.stdout)
            self.assertFalse((output / "ca.sqlite3").exists())
            self.assertTrue(list((output / "reports").glob("*-invalid.md")))

    def test_bad_zip_exits_one(self):
        with tempfile.TemporaryDirectory() as folder:
            invalid = Path(folder) / "bad.xlsx"
            invalid.write_bytes(b"not a workbook")
            result = self.run_import(invalid, Path(folder) / "output")
            self.assertEqual(result.returncode, 1)
            self.assertIn("Error:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
