from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from conformance.federation import Gateway

QUERY='query($ids:[ID!]!){customerOverviews(ids:$ids){id displayName tickets{id title status} partial sources{sourceId status}}}'
class FederationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        crm=sqlite3.connect(root/'crm.sqlite');tickets=sqlite3.connect(root/'tickets.sqlite')
        crm.executescript("CREATE TABLE customers(tenant TEXT,id TEXT,display_name TEXT,PRIMARY KEY(tenant,id)); INSERT INTO customers VALUES('a','1','A'),('a','2','B'),('b','1','Private');")
        tickets.executescript("CREATE TABLE tickets(tenant TEXT,id TEXT,customer_id TEXT,title TEXT,status TEXT,PRIMARY KEY(tenant,id)); CREATE INDEX ticket_customer ON tickets(tenant,customer_id,id); INSERT INTO tickets VALUES('a','t1','1','One','open'),('a','t2','2','Two','closed'),('b','t3','1','Secret','open');")
        crm.close();tickets.close();self.gateway=Gateway(root/'crm.sqlite',root/'tickets.sqlite','a')
    def tearDown(self):self.gateway.close();self.temp.cleanup()
    def test_batched_join_has_one_query_per_source(self):
        result=self.gateway.execute(QUERY,{'ids':['1','2']})
        self.assertIsNone(result.errors);self.assertEqual(len(result.data['customerOverviews']),2)
        self.assertEqual(self.gateway.counts,{'crm':1,'tickets':1})
    def test_tenant_does_not_leak(self):
        result=self.gateway.execute(QUERY,{'ids':['1']})
        self.assertNotIn('Secret',str(result.data));self.assertNotIn('Private',str(result.data))
    def test_unavailable_source_is_not_empty_success(self):
        self.gateway.tickets.close();result=self.gateway.execute(QUERY,{'ids':['1']})
        row=result.data['customerOverviews'][0]
        self.assertTrue(row['partial']);self.assertIsNone(row['tickets'])
    def test_key_budget_before_database(self):
        result=self.gateway.execute(QUERY,{'ids':[str(i) for i in range(26)]})
        self.assertTrue(result.errors);self.assertEqual(self.gateway.counts,{'crm':0,'tickets':0})

if __name__=='__main__':unittest.main()
