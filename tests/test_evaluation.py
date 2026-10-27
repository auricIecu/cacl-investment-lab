import json
import subprocess
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from examples.phase3_synthetic import make_dataset
from cacl_ca.workbook import read_workbook, extract_ca
from cacl_ca.reconcile import reconcile
from cacl_ca.storage import save_import
from tests.support import source_path


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=extract_ca(read_workbook(source_path()))
        cls.report=reconcile(cls.snapshot)

    def prepare(self,folder):
        db=Path(folder)/'ca.sqlite3'
        save_import(db,source_path(),self.snapshot,self.report)
        return db

    def run_cli(self,db,output,dataset=None):
        command=[sys.executable,'-m','cacl_ca','evaluate','--db',str(db),'--revision','1','--output-dir',str(output)]
        if dataset: command+=['--dataset',str(dataset)]
        return subprocess.run(command,capture_output=True,text=True)

    def test_missing_data_reports_gap_not_zero_return_and_preserves_db(self):
        with tempfile.TemporaryDirectory() as folder:
            db=self.prepare(folder)
            original=sha256(db.read_bytes()).hexdigest()
            out=Path(folder)/'evaluation'
            result=self.run_cli(db,out)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertIn('data_insufficient',result.stdout)
            report=json.loads(next(out.glob('evaluation-*.json')).read_text())
            self.assertIsNone(report['base'])
            self.assertFalse(report['ready_for_paper'])
            self.assertEqual(len(report['universe']),72)
            self.assertEqual(sha256(db.read_bytes()).hexdigest(),original)

    def test_synthetic_report_is_reproducible_and_not_a_return_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            db=self.prepare(folder)
            data=Path(folder)/'synthetic.json'
            data.write_text(json.dumps(make_dataset()))
            out=Path(folder)/'evaluation'
            result=self.run_cli(db,out,data)
            self.assertEqual(result.returncode,0,result.stderr)
            path=next(out.glob('evaluation-*.json'))
            before=path.read_bytes()
            report=json.loads(before)
            self.assertEqual(report['status'],'synthetic_only')
            self.assertEqual(report['performance_validation'],'not_established')
            self.assertFalse(report['ready_for_paper'])
            self.assertIsNotNone(report['base']['metrics'])
            again=self.run_cli(db,out,data)
            self.assertEqual(again.returncode,0,again.stderr)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(len(list(out.glob('evaluation-*.json'))),1)
            self.assertIn('SINTÉTICOS',next(out.glob('evaluation-*.md')).read_text())

    def test_invalid_dataset_exits_one_without_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            db=self.prepare(folder)
            data=Path(folder)/'bad.json'
            data.write_text('{"schema_version": 999}')
            result=self.run_cli(db,Path(folder)/'out',data)
            self.assertEqual(result.returncode,1)
            self.assertIn('Error:',result.stderr)
            self.assertNotIn('Traceback',result.stderr)

    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/'absent.sqlite3'
            result=self.run_cli(db,Path(folder)/'out')
            self.assertEqual(result.returncode,1)
            self.assertFalse(db.exists())
