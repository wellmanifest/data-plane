import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from sqlite_audit import audit, quote_identifier

class SQLiteAudit(unittest.TestCase):
    def test_wal_snapshot_mixed_types_and_safe_identifiers(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'source.sqlite'
            writer=sqlite3.connect(path)
            try:
                writer.execute('PRAGMA journal_mode=WAL')
                writer.execute('PRAGMA wal_autocheckpoint=0')
                name='odd"; DROP TABLE victim; --'
                q=quote_identifier(name)
                writer.execute(f'CREATE TABLE {q} (id INTEGER PRIMARY KEY, value)')
                writer.execute('CREATE TABLE victim (id INTEGER PRIMARY KEY)')
                writer.executemany(f'INSERT INTO {q}(value) VALUES (?)',[(1,),('secret-row-content',),(None,),(b'bytes',)])
                writer.commit()
                self.assertTrue(Path(str(path)+'-wal').exists())
                before=list(writer.execute(f'SELECT * FROM {q}'))
                report=audit(path)
                table=next(t for t in report['tables'] if t['name']==name)
                self.assertEqual(table['rowCount'],4)
                self.assertEqual(table['storageTypes']['value'],{'blob':1,'integer':1,'null':1,'text':1})
                self.assertNotIn('secret-row-content',json.dumps(report))
                self.assertEqual(before,list(writer.execute(f'SELECT * FROM {q}')))
                self.assertEqual(writer.execute('SELECT COUNT(*) FROM victim').fetchone()[0],0)
                self.assertTrue(report['complete'])
                self.assertTrue(report['integrity']['ok'])
            finally: writer.close()

    def test_foreign_key_orphan_reported_without_row_data(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'source.sqlite'
            con=sqlite3.connect(path)
            con.executescript('CREATE TABLE parent(id INTEGER PRIMARY KEY); CREATE TABLE child(id INTEGER PRIMARY KEY,pid INTEGER REFERENCES parent(id)); INSERT INTO child VALUES(1,42);')
            con.close()
            report=audit(path)
            self.assertEqual(report['foreignKeyViolationCount'],1)
            self.assertFalse(report['migrationReady'])

    def test_cli_refuses_overwriting_database(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'source.sqlite'
            con=sqlite3.connect(path); con.execute('CREATE TABLE t(id INTEGER)'); con.close()
            before=path.read_bytes()
            result=subprocess.run([sys.executable,str(ROOT/'tools/sqlite_audit.py'),str(path),'--output',str(path)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(path.read_bytes(),before)

    def test_missing_source_not_created(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'missing.sqlite'
            with self.assertRaises(FileNotFoundError): audit(path)
            self.assertFalse(path.exists())

    def test_timeout_is_not_silent_partial_success(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'source.sqlite'
            con=sqlite3.connect(path); con.execute('CREATE TABLE t(id INTEGER)'); con.close()
            with self.assertRaises(TimeoutError): audit(path,timeout=1e-12)

if __name__=='__main__': unittest.main()
