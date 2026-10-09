"""Executable bounded GraphQL fixture over two SQLite sources; not a server."""
import json
import sqlite3
from datetime import datetime,timezone
from graphql import build_schema,graphql_sync

SDL='''
type SourceState { sourceId: String!, status: String!, observedAt: String!, version: String }
type Ticket { id: ID!, title: String!, status: String! }
type CustomerOverview { id: ID!, displayName: String!, tickets: [Ticket!], sources: [SourceState!]!, partial: Boolean! }
type Query { customerOverview(id: ID!): CustomerOverview, customerOverviews(ids: [ID!]!): [CustomerOverview!]! }
'''

class Gateway:
    def __init__(self,crm_path,tickets_path,tenant):
        self.tenant=tenant;self.counts={'crm':0,'tickets':0}
        self.crm=sqlite3.connect(crm_path);self.tickets=sqlite3.connect(tickets_path)
        for con in [self.crm,self.tickets]:
            con.row_factory=sqlite3.Row
            con.execute('PRAGMA query_only=ON');con.execute('PRAGMA cache_size=-2048');con.execute('PRAGMA mmap_size=0')
        self.schema=build_schema(SDL)
        self.schema.get_type('Query').fields['customerOverviews'].resolve=lambda _root,_info,ids:self.overviews(ids)
        self.schema.get_type('Query').fields['customerOverview'].resolve=lambda _root,_info,id:next(iter(self.overviews([id])),None)

    def overviews(self,ids):
        if not 1<=len(ids)<=25 or any(len(str(i))>64 for i in ids): raise ValueError('Key budget exceeded')
        ids=list(dict.fromkeys(str(i) for i in ids));slots=','.join('?' for _ in ids)
        now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
        self.counts['crm']+=1
        rows=self.crm.execute(f'SELECT id,substr(display_name,1,80) AS display_name FROM customers WHERE tenant=? AND id IN ({slots}) ORDER BY id',(self.tenant,*ids)).fetchall()
        if not rows:return []
        keys=[r['id'] for r in rows];slots=','.join('?' for _ in keys)
        by_customer={k:[] for k in keys};partial=False
        try:
            self.counts['tickets']+=1
            tickets=self.tickets.execute(f'''SELECT id,customer_id,title,status FROM (
              SELECT id,customer_id,substr(title,1,64) AS title,substr(status,1,24) AS status,
              row_number() OVER(PARTITION BY customer_id ORDER BY id) AS row_rank
              FROM tickets WHERE tenant=? AND customer_id IN ({slots})
            ) WHERE row_rank<=10 ORDER BY customer_id,id''',(self.tenant,*keys))
            for t in tickets:by_customer[t['customer_id']].append({'id':t['id'],'title':t['title'],'status':t['status']})
        except sqlite3.Error:
            partial=True
        sources=[{'sourceId':'crm','status':'available','observedAt':now,'version':None},
                 {'sourceId':'tickets','status':'unavailable' if partial else 'available','observedAt':now,'version':None}]
        result=[{'id':r['id'],'displayName':r['display_name'],'tickets':None if partial else by_customer[r['id']],'sources':sources,'partial':partial} for r in rows]
        if len(json.dumps(result,ensure_ascii=False).encode())>32768:raise ValueError('Response byte budget exceeded')
        return result

    def execute(self,query,variables=None):
        # Fixture query execution only. Production requires depth/alias/overall cost limits.
        return graphql_sync(self.schema,query,variable_values=variables)

    def close(self):self.crm.close();self.tickets.close()
