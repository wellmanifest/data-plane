"""Bounded SQLite ES protocol model. No production authorization or network server."""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

ZERO='0'*64
MAX_EVENT_BYTES=16384
MAX_BATCH_BYTES=262144
MAX_BATCH_ROWS=64
MAX_INT=2**63-1
URN=re.compile(r'^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
DEC=re.compile(r'^(0|[1-9][0-9]*)$')
SIGNED=re.compile(r'^(0|-?[1-9][0-9]*)$')
EVENT_FIELDS={'schema','eventUrn','tenantId','streamUrn','streamVersion','eventType','schemaVersion','processUri','commandId','correlationId','causationUrn','occurredAt','authorityId','authorityEpoch','planHash','inputHash','previousHash','eventHash','data'}

class Conflict(ValueError): pass
class IntegrityError(ValueError): pass

def canonical(value):
    def check(item):
        if isinstance(item,float): raise ValueError('Float is outside canonical profile')
        if isinstance(item,int) and not isinstance(item,bool) and abs(item)>2**53-1:
            raise ValueError('Large integers must use decimal strings')
        if isinstance(item,dict):
            if any(not isinstance(k,str) for k in item): raise ValueError('Non-string key')
            for val in item.values(): check(val)
        elif isinstance(item,list):
            for val in item: check(val)
    check(value)
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def digest(value): return hashlib.sha256(canonical(value)).hexdigest()
def event_hash(event): return digest({k:v for k,v in event.items() if k!='eventHash'})
def new_urn(): return 'urn:uuid:'+str(uuid.uuid4())

def decode_event(raw):
    if isinstance(raw,str): raw=raw.encode('utf-8')
    if len(raw)>MAX_EVENT_BYTES: raise IntegrityError('Event exceeds byte limit')
    def pairs(items):
        out={}
        for k,v in items:
            if k in out: raise IntegrityError('Duplicate JSON key')
            out[k]=v
        return out
    event=json.loads(raw,object_pairs_hook=pairs)
    validate_event(event)
    if canonical(event)!=raw: raise IntegrityError('Non-canonical event bytes')
    return event

def validate_event(e):
    if not isinstance(e,dict) or set(e)!=EVENT_FIELDS: raise IntegrityError('Closed envelope mismatch')
    if e['schema']!='data-plane.domain-event/v1' or e['eventType']!='counter.changed' or type(e['schemaVersion']) is not int or e['schemaVersion']!=1:
        raise IntegrityError('Unknown domain event contract')
    for key in ['eventUrn','streamUrn']:
        if not isinstance(e[key],str) or not URN.fullmatch(e[key]): raise IntegrityError('Invalid URN')
    if e['causationUrn'] is not None and (not isinstance(e['causationUrn'],str) or not URN.fullmatch(e['causationUrn'])):
        raise IntegrityError('Invalid causation')
    for key in ['tenantId','commandId','correlationId']:
        if str(uuid.UUID(e[key]))!=e[key]: raise IntegrityError('Noncanonical UUID')
    for key in ['streamVersion','authorityEpoch']:
        if not isinstance(e[key],str) or not DEC.fullmatch(e[key]) or not 1<=int(e[key])<=MAX_INT:
            raise IntegrityError('Invalid version')
    if not re.fullmatch(r'authority:[a-z0-9._-]{1,64}',e['authorityId']): raise IntegrityError('Invalid authority')
    if e['processUri']!='process://data-gateway/counter.change/v2': raise IntegrityError('Unknown process')
    if not e['occurredAt'].endswith('Z'): raise IntegrityError('UTC required')
    datetime.fromisoformat(e['occurredAt'].replace('Z','+00:00'))
    for key in ['inputHash','planHash','previousHash','eventHash']:
        if not isinstance(e[key],str) or not re.fullmatch('[0-9a-f]{64}',e[key]): raise IntegrityError('Invalid hash')
    if not isinstance(e['data'],dict) or set(e['data'])!={'delta'}: raise IntegrityError('Unknown payload')
    delta=e['data']['delta']
    if not isinstance(delta,str) or not SIGNED.fullmatch(delta) or not -MAX_INT-1<=int(delta)<=MAX_INT:
        raise IntegrityError('Invalid delta')
    if event_hash(e)!=e['eventHash']: raise IntegrityError('Event hash mismatch')
    if len(canonical(e))>MAX_EVENT_BYTES: raise IntegrityError('Event exceeds byte limit')

DDL='''
CREATE TABLE IF NOT EXISTS heads (
 tenant TEXT NOT NULL, stream TEXT NOT NULL, version INTEGER NOT NULL,
 hash TEXT NOT NULL, authority TEXT NOT NULL, epoch INTEGER NOT NULL,
 PRIMARY KEY(tenant,stream));
CREATE TABLE IF NOT EXISTS events (
 event_urn TEXT PRIMARY KEY, tenant TEXT NOT NULL, stream TEXT NOT NULL,
 version INTEGER NOT NULL, hash TEXT NOT NULL, canonical BLOB NOT NULL,
 UNIQUE(tenant,stream,version));
CREATE TABLE IF NOT EXISTS receipts (
 tenant TEXT NOT NULL, subject TEXT NOT NULL, operation TEXT NOT NULL,
 key TEXT NOT NULL, input_hash TEXT NOT NULL, event_urn TEXT NOT NULL,
 PRIMARY KEY(tenant,subject,operation,key), FOREIGN KEY(event_urn) REFERENCES events(event_urn));
CREATE TABLE IF NOT EXISTS outbox (
 event_urn TEXT PRIMARY KEY, delivered INTEGER NOT NULL DEFAULT 0,
 FOREIGN KEY(event_urn) REFERENCES events(event_urn));
CREATE TABLE IF NOT EXISTS counters (
 tenant TEXT NOT NULL, stream TEXT NOT NULL, value INTEGER NOT NULL,
 version INTEGER NOT NULL, hash TEXT NOT NULL,
 PRIMARY KEY(tenant,stream));
CREATE TRIGGER IF NOT EXISTS immutable_event_update BEFORE UPDATE ON events
 BEGIN SELECT RAISE(ABORT,'immutable event'); END;
CREATE TRIGGER IF NOT EXISTS immutable_event_delete BEFORE DELETE ON events
 BEGIN SELECT RAISE(ABORT,'immutable event'); END;
'''

class Store:
    def __init__(self,path,authority='authority:local',epoch=1):
        self.path=Path(path); self.authority=authority; self.epoch=epoch
        self.db=sqlite3.connect(self.path,timeout=5,isolation_level=None)
        self.db.row_factory=sqlite3.Row
        for sql in ['PRAGMA foreign_keys=ON','PRAGMA journal_mode=WAL','PRAGMA synchronous=FULL','PRAGMA cache_size=-2048','PRAGMA mmap_size=0','PRAGMA temp_store=FILE']:
            self.db.execute(sql)
        self.db.executescript(DDL)

    def close(self): self.db.close()
    def _head(self,tenant,stream):
        return self.db.execute('SELECT * FROM heads WHERE tenant=? AND stream=?',(tenant,stream)).fetchone()

    def _project(self,event):
        tenant,stream=event['tenantId'],event['streamUrn']
        row=self.db.execute('SELECT * FROM counters WHERE tenant=? AND stream=?',(tenant,stream)).fetchone()
        version=0 if row is None else row['version']
        old_hash=ZERO if row is None else row['hash']
        if int(event['streamVersion'])!=version+1 or event['previousHash']!=old_hash:
            raise IntegrityError('Projection gap or chain mismatch')
        value=(0 if row is None else row['value'])+int(event['data']['delta'])
        if not -MAX_INT-1<=value<=MAX_INT: raise IntegrityError('Counter overflow')
        self.db.execute('INSERT INTO counters VALUES (?,?,?,?,?) ON CONFLICT(tenant,stream) DO UPDATE SET value=excluded.value,version=excluded.version,hash=excluded.hash',
                        (tenant,stream,value,int(event['streamVersion']),event['eventHash']))

    def _insert(self,event,outbound=False):
        validate_event(event)
        raw=canonical(event)
        existing=self.db.execute('SELECT canonical FROM events WHERE event_urn=?',(event['eventUrn'],)).fetchone()
        if existing:
            if bytes(existing['canonical'])!=raw: raise IntegrityError('Duplicate ID with different bytes')
            return False
        head=self._head(event['tenantId'],event['streamUrn'])
        version=0 if head is None else head['version']
        previous=ZERO if head is None else head['hash']
        if int(event['streamVersion'])!=version+1 or event['previousHash']!=previous:
            raise IntegrityError('Stream gap or chain mismatch')
        if head and (head['authority']!=event['authorityId'] or head['epoch']!=int(event['authorityEpoch'])):
            raise Conflict('Authority change requires separately verified handoff')
        self.db.execute('INSERT INTO events VALUES (?,?,?,?,?,?)',(event['eventUrn'],event['tenantId'],event['streamUrn'],int(event['streamVersion']),event['eventHash'],raw))
        self.db.execute('INSERT INTO heads VALUES (?,?,?,?,?,?) ON CONFLICT(tenant,stream) DO UPDATE SET version=excluded.version,hash=excluded.hash',
                        (event['tenantId'],event['streamUrn'],int(event['streamVersion']),event['eventHash'],event['authorityId'],int(event['authorityEpoch'])))
        self._project(event)
        if outbound: self.db.execute('INSERT INTO outbox(event_urn) VALUES (?)',(event['eventUrn'],))
        return True

    def append(self,tenant,stream,delta,expected_version,key,subject='service:fixture',fail_before_commit=False):
        """Trusted conformance call. Production handler must verify plan/admission first."""
        operation='process://data-gateway/counter.change/v2'
        command={'tenant':tenant,'stream':stream,'delta':str(delta),'expectedVersion':str(expected_version),'authority':self.authority,'epoch':str(self.epoch)}
        input_hash=digest(command)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            receipt=self.db.execute('SELECT * FROM receipts WHERE tenant=? AND subject=? AND operation=? AND key=?',(tenant,subject,operation,key)).fetchone()
            if receipt:
                if receipt['input_hash']!=input_hash: raise Conflict('Idempotency conflict')
                raw=self.db.execute('SELECT canonical FROM events WHERE event_urn=?',(receipt['event_urn'],)).fetchone()[0]
                self.db.execute('COMMIT'); return decode_event(raw)
            head=self._head(tenant,stream)
            if (0 if head is None else head['version'])!=expected_version: raise Conflict('Expected version conflict')
            if head and (head['authority']!=self.authority or head['epoch']!=self.epoch): raise Conflict('Writer is not authority')
            event={'schema':'data-plane.domain-event/v1','eventUrn':new_urn(),'tenantId':tenant,'streamUrn':stream,
                   'streamVersion':str(expected_version+1),'eventType':'counter.changed','schemaVersion':1,
                   'processUri':operation,'commandId':str(uuid.uuid4()),'correlationId':str(uuid.uuid4()),'causationUrn':None,
                   'occurredAt':datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z'),
                   'authorityId':self.authority,'authorityEpoch':str(self.epoch),'planHash':digest({'fixturePlan':command}),
                   'inputHash':input_hash,'previousHash':ZERO if head is None else head['hash'],'data':{'delta':str(delta)}}
            event['eventHash']=event_hash(event)
            self._insert(event,outbound=True)
            self.db.execute('INSERT INTO receipts VALUES (?,?,?,?,?,?)',(tenant,subject,operation,key,input_hash,event['eventUrn']))
            if fail_before_commit: raise RuntimeError('Injected transaction failure')
            self.db.execute('COMMIT'); return event
        except BaseException:
            if self.db.in_transaction: self.db.execute('ROLLBACK')
            raise

    def ingest(self,raw):
        event=decode_event(raw)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            inserted=self._insert(event)
            self.db.execute('COMMIT'); return inserted
        except BaseException:
            self.db.execute('ROLLBACK'); raise

    def pending(self,limit=MAX_BATCH_ROWS,max_bytes=MAX_BATCH_BYTES):
        if not 1<=limit<=MAX_BATCH_ROWS or not MAX_EVENT_BYTES<=max_bytes<=MAX_BATCH_BYTES:
            raise ValueError('Batch exceeds profile')
        # This is local committed order under SQLite single-writer, not a PG BIGSERIAL cursor.
        cursor=self.db.execute('SELECT e.event_urn,e.canonical FROM outbox o JOIN events e USING(event_urn) WHERE o.delivered=0 ORDER BY e.rowid LIMIT ?',(limit,))
        total=0
        for row in cursor:
            raw=bytes(row['canonical'])
            if total+len(raw)>max_bytes: break
            total+=len(raw); yield row['event_urn'],raw

    def ack(self,event_urn): self.db.execute('UPDATE outbox SET delivered=1 WHERE event_urn=?',(event_urn,))
    def value(self,tenant,stream):
        row=self.db.execute('SELECT value FROM counters WHERE tenant=? AND stream=?',(tenant,stream)).fetchone()
        return None if row is None else row[0]

    def rebuild(self):
        """Offline fixture replay. Production uses a shadow projection then swaps alias."""
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('DELETE FROM counters')
            for row in self.db.execute('SELECT canonical FROM events ORDER BY tenant,stream,version'):
                self._project(decode_event(row[0]))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK'); raise

def relay(source,target,fail_after_target_commit=False):
    count=0
    # Buffer a bounded batch to avoid a long source read transaction during ACKs.
    batch=list(source.pending())
    for event_urn,raw in batch:
        target.ingest(raw)
        if fail_after_target_commit: raise RuntimeError('Injected crash before source ACK')
        source.ack(event_urn); count+=1
    return count
