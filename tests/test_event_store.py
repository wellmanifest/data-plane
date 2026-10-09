import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from conformance.event_store import Store,Conflict,IntegrityError,canonical,event_hash,relay,decode_event
TENANT='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
OTHER='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
STREAM='urn:uuid:11111111-1111-4111-8111-111111111111'

class EventStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=Store(self.root/'source.sqlite');self.target=Store(self.root/'target.sqlite',authority='authority:replica')
    def tearDown(self):self.source.close();self.target.close();self.temp.cleanup()

    def test_atomic_event_projection_receipt_outbox_rollback(self):
        with self.assertRaises(RuntimeError):self.source.append(TENANT,STREAM,3,0,'x',fail_before_commit=True)
        for table in ['heads','events','receipts','outbox','counters']:
            self.assertEqual(self.source.db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)

    def test_retry_and_conflicting_idempotency(self):
        one=self.source.append(TENANT,STREAM,3,0,'x')
        self.assertEqual(self.source.append(TENANT,STREAM,3,0,'x'),one)
        self.assertEqual(self.source.value(TENANT,STREAM),3)
        with self.assertRaises(Conflict):self.source.append(TENANT,STREAM,4,0,'x')

    def test_two_concurrent_writers_same_expected_version(self):
        path=self.source.path
        def write(i):
            con=Store(path)
            try:con.append(TENANT,STREAM,1,0,str(i));return True
            except Conflict:return False
            finally:con.close()
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(write,[1,2]))
        self.assertEqual(sum(result),1);self.assertEqual(self.source.value(TENANT,STREAM),1)

    def test_crash_after_destination_commit_then_retry(self):
        self.source.append(TENANT,STREAM,3,0,'x')
        with self.assertRaises(RuntimeError):relay(self.source,self.target,fail_after_target_commit=True)
        self.assertEqual(self.target.value(TENANT,STREAM),3)
        self.assertEqual(relay(self.source,self.target),1)
        self.assertEqual(self.target.value(TENANT,STREAM),3)
        self.assertEqual(list(self.source.pending()),[])

    def test_gap_and_tamper_are_rejected(self):
        one=self.source.append(TENANT,STREAM,3,0,'a');two=self.source.append(TENANT,STREAM,4,1,'b')
        with self.assertRaises(IntegrityError):self.target.ingest(canonical(two))
        changed=copy.deepcopy(one);changed['data']['delta']='100'
        with self.assertRaises(IntegrityError):self.target.ingest(canonical(changed))
        self.target.ingest(canonical(one));changed['eventHash']=event_hash(changed)
        with self.assertRaises(IntegrityError):self.target.ingest(canonical(changed))

    def test_rebuild_is_deterministic_without_external_effects(self):
        for i,delta in enumerate([3,-1,7]):self.source.append(TENANT,STREAM,delta,i,str(i))
        relay(self.source,self.target)
        before=self.target.value(TENANT,STREAM)
        self.target.rebuild();self.target.rebuild()
        self.assertEqual(self.target.value(TENANT,STREAM),before)
        self.assertEqual(list(self.target.pending()),[])

    def test_authority_mismatch_rejected(self):
        self.source.append(TENANT,STREAM,1,0,'x');self.source.authority='authority:other'
        with self.assertRaises(Conflict):self.source.append(TENANT,STREAM,1,1,'y')

    def test_history_cannot_be_updated_or_deleted(self):
        self.source.append(TENANT,STREAM,1,0,'x')
        for sql in ['UPDATE events SET hash=hash','DELETE FROM events']:
            with self.assertRaises(sqlite3.IntegrityError):self.source.db.execute(sql)

    def test_batch_limits_and_tenant_partition(self):
        for i in range(70):self.source.append(TENANT,STREAM,1,i,str(i))
        self.source.append(OTHER,STREAM,9,0,'other')
        batch=list(self.source.pending());self.assertEqual(len(batch),64)
        self.assertLessEqual(sum(len(raw) for _,raw in batch),262144)
        self.assertEqual(self.source.value(TENANT,STREAM),70);self.assertEqual(self.source.value(OTHER,STREAM),9)

    def test_restart_preserves_deduplication(self):
        one=self.source.append(TENANT,STREAM,2,0,'x');path=self.source.path
        self.source.close();self.source=Store(path)
        self.assertEqual(self.source.append(TENANT,STREAM,2,0,'x'),one)

    def test_canonical_rejects_duplicate_keys_and_float(self):
        with self.assertRaises(ValueError):canonical({'x':1.2})
        with self.assertRaises(IntegrityError):decode_event(b'{"schema":"x","schema":"y"}')

    def test_overflow_rolls_back_entire_command(self):
        self.source.append(TENANT,STREAM,2**63-1,0,'x')
        with self.assertRaises(IntegrityError):self.source.append(TENANT,STREAM,1,1,'y')
        self.assertEqual(self.source._head(TENANT,STREAM)['version'],1)

if __name__=='__main__':unittest.main()
