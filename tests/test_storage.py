import sqlite3
from contextlib import closing
import tempfile
import unittest
import zipfile
from hashlib import sha256
from pathlib import Path

from cacl_ca.workbook import read_workbook, extract_ca
from cacl_ca.reconcile import reconcile
from cacl_ca.storage import save_import
from tests.support import source_path


class StorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = extract_ca(read_workbook(source_path()))
        cls.report = reconcile(cls.snapshot)

    def test_same_source_is_one_revision_and_stored_snapshot_is_immutable(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "ca.sqlite3"
            first = save_import(db, source_path(), self.snapshot, self.report)
            changed_report = dict(self.report, status="reconciled")
            again = save_import(db, source_path(), self.snapshot, changed_report)
            self.assertEqual(first, (1, True))
            self.assertEqual(again, (1, False))
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM imports").fetchone()[0], 1)
                self.assertIn('"review_required"', con.execute("SELECT report_json FROM imports").fetchone()[0])

    def test_new_bytes_create_a_revision_and_original_is_unchanged(self):
        original = source_path().read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "ca.sqlite3"
            save_import(db, source_path(), self.snapshot, self.report)
            other = Path(folder) / "revision.xlsx"
            other.write_bytes(original)
            with zipfile.ZipFile(other, "a") as archive:
                archive.comment = b"revision-test"
            snapshot = extract_ca(read_workbook(other))
            self.assertEqual(save_import(db, other, snapshot, reconcile(snapshot)), (2, True))
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM imports").fetchone()[0], 2)
            self.assertEqual(len(list((Path(folder) / "sources").glob("*.xlsx"))), 2)
        self.assertEqual(source_path().read_bytes(), original)

    def test_changed_source_hash_is_rejected_before_insertion(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "ca.sqlite3"
            snapshot = dict(self.snapshot, source_sha256="0" * 64)
            with self.assertRaisesRegex(ValueError, "hash"):
                save_import(db, source_path(), snapshot, self.report)
            self.assertFalse(db.exists())

    def test_invalid_data_is_not_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "ca.sqlite3"
            report = dict(self.report, status="invalid")
            with self.assertRaises(ValueError):
                save_import(db, source_path(), self.snapshot, report)
            self.assertFalse(db.exists())

    def test_corrupt_archive_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "ca.sqlite3"
            archive = Path(folder) / "sources" / f"{self.snapshot['source_sha256']}.xlsx"
            archive.parent.mkdir()
            archive.write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "archivo"):
                save_import(db, source_path(), self.snapshot, self.report)
            self.assertEqual(archive.read_bytes(), b"corrupt")

    def test_archive_matches_input_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            save_import(Path(folder) / "ca.sqlite3", source_path(), self.snapshot, self.report)
            archived = next((Path(folder) / "sources").glob("*.xlsx"))
            self.assertEqual(sha256(archived.read_bytes()).hexdigest(), self.snapshot["source_sha256"])

    def test_failed_insert_preserves_previous_revision_and_can_be_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "ca.sqlite3"
            save_import(db, source_path(), self.snapshot, self.report)
            other = Path(folder) / "revision.xlsx"
            other.write_bytes(source_path().read_bytes())
            with zipfile.ZipFile(other, "a") as archive:
                archive.comment = b"retry-test"
            snapshot = extract_ca(read_workbook(other))
            report = reconcile(snapshot)
            with closing(sqlite3.connect(db)) as con:
                con.execute("""CREATE TRIGGER reject_insert BEFORE INSERT ON imports
                    BEGIN SELECT RAISE(ABORT, 'test failure'); END""")
            with self.assertRaises(sqlite3.IntegrityError):
                save_import(db, other, snapshot, report)
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM imports").fetchone()[0], 1)
                con.execute("DROP TRIGGER reject_insert")
            self.assertEqual(save_import(db, other, snapshot, report), (2, True))
