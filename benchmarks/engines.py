#!/usr/bin/env python3
"""Storage-engine A/B for the data-plane write/read pattern: SQLite, SQLite+group commit, PostgreSQL, PGlite.

One configuration per process (clean RSS): `python3 benchmarks/engines.py --engine E --clients C --n N [--dsn DSN] [--path P]`.
Every engine performs the same transactional work as the data-gateway kernel:
  command: receipt lookup, stream head, event (~1 KB), blob (512 B), resource, receipt, chained audit (~0.8 KB)
  query:   resource+blob read, chained audit
The audit chain head is a one-row table updated inside the transaction (single writer of the chain).
Durability: SQLite synchronous=FULL; PostgreSQL/PGlite fsync and synchronous_commit as configured by the server.
Engines: sqlite, sqlite-normal-reads, sqlite-group (group commit), postgres and pglite (both need --dsn; --server-pid
samples the server process tree RSS). Results and method: docs/analysis/storage-engines.md.
"""
from __future__ import annotations
import argparse, hashlib, json, os, queue, resource, statistics, threading, time, uuid

DDL = [
    "CREATE TABLE events (id INTEGER PRIMARY KEY, stream TEXT NOT NULL, version INTEGER NOT NULL, hash TEXT NOT NULL, body {B} NOT NULL, UNIQUE(stream, version))",
    "CREATE TABLE blobs (sha TEXT PRIMARY KEY, content {B} NOT NULL)",
    "CREATE TABLE resources (urn TEXT PRIMARY KEY, sha TEXT NOT NULL, media TEXT NOT NULL, len INTEGER NOT NULL, version INTEGER NOT NULL)",
    "CREATE TABLE receipts (op TEXT NOT NULL, key TEXT NOT NULL, input_hash TEXT NOT NULL, result {B} NOT NULL, PRIMARY KEY(op, key))",
    "CREATE TABLE audit (seq INTEGER PRIMARY KEY, hash TEXT NOT NULL, body {B} NOT NULL)",
    "CREATE TABLE audit_head (id INTEGER PRIMARY KEY, seq INTEGER NOT NULL, hash TEXT NOT NULL)",
    "INSERT INTO audit_head VALUES (1, 0, '0000000000000000000000000000000000000000000000000000000000000000')",
]
TABLES = ['events', 'blobs', 'resources', 'receipts', 'audit', 'audit_head']


def body(kind, i, size):
    record = {'kind': kind, 'i': i, 'pad': 'x' * size, 'schema': 'data-plane.domain-event/v1', 'tenantId': str(uuid.UUID(int=i))}
    return json.dumps(record, sort_keys=True, separators=(',', ':')).encode()


def audit_append(cur, ph, request_id):
    cur.execute(f"SELECT seq, hash FROM audit_head WHERE id = 1{' FOR UPDATE' if ph == '%s' else ''}")
    seq, previous = cur.fetchone()
    record = body('audit', seq + 1, 560)[:-1] + b',"previousHash":"' + previous.encode() + b'","requestId":"' + request_id.encode() + b'"}'
    digest = hashlib.sha256(record).hexdigest()
    cur.execute(f"INSERT INTO audit VALUES ({ph},{ph},{ph})", (seq + 1, digest, record))
    cur.execute(f"UPDATE audit_head SET seq = {ph}, hash = {ph} WHERE id = 1", (seq + 1, digest))


def command(cur, ph, i):
    key, urn = f'k{i}', f'urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, str(i))}'
    cur.execute(f"SELECT input_hash FROM receipts WHERE op = {ph} AND key = {ph}", ('resource.publish', key))
    if cur.fetchone(): return False
    cur.execute(f"SELECT max(version) FROM events WHERE stream = {ph}", (urn,)); cur.fetchone()
    content = (f'{i:08d}'.encode() * 64)[:512]; sha = hashlib.sha256(content).hexdigest()
    event = body('event', i, 700)
    cur.execute(f"INSERT INTO events (stream, version, hash, body) VALUES ({ph},{ph},{ph},{ph})", (urn, 1, hashlib.sha256(event).hexdigest(), event))
    cur.execute(f"INSERT INTO blobs VALUES ({ph},{ph}) ON CONFLICT (sha) DO NOTHING", (sha, content))
    cur.execute(f"INSERT INTO resources VALUES ({ph},{ph},{ph},{ph},{ph})", (urn, sha, 'text/plain', 512, 1))
    cur.execute(f"INSERT INTO receipts VALUES ({ph},{ph},{ph},{ph})", ('resource.publish', key, sha, body('result', i, 120)))
    audit_append(cur, ph, str(uuid.uuid5(uuid.NAMESPACE_DNS, key)))
    return True


def query(cur, ph, i):
    urn = f'urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, str(i))}'
    cur.execute(f"SELECT r.sha, r.media, b.content FROM resources r JOIN blobs b ON b.sha = r.sha WHERE r.urn = {ph}", (urn,))
    assert cur.fetchone() is not None
    audit_append(cur, ph, str(uuid.uuid5(uuid.NAMESPACE_DNS, f'q{i}')))


class SQLite:
    ph, blob = '?', 'BLOB'
    def __init__(self, path, read_sync='FULL'):
        import sqlite3
        self.sqlite3, self.path, self.read_sync = sqlite3, path, read_sync
    def connect(self):
        db = self.sqlite3.connect(self.path, isolation_level=None, timeout=60, check_same_thread=False)
        for pragma in ('journal_mode=WAL', 'synchronous=FULL', 'cache_size=-2048', 'busy_timeout=60000'): db.execute('PRAGMA ' + pragma)
        return db
    def setup(self):
        for p in (self.path, self.path + '-wal', self.path + '-shm'):
            if os.path.exists(p): os.remove(p)
        db = self.connect()
        for s in DDL: db.execute(s.format(B=self.blob))
        db.close()
    def run(self, db, fn, i, write):
        if not write: db.execute(f'PRAGMA synchronous={self.read_sync}')
        cur = db.cursor(); cur.execute('BEGIN IMMEDIATE')
        try: fn(cur, self.ph, i); cur.execute('COMMIT')
        except BaseException: cur.execute('ROLLBACK'); raise
        finally:
            if not write: db.execute('PRAGMA synchronous=FULL')
    def size(self):
        db = self.connect(); db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        try: total = db.execute('SELECT sum(pgsize) FROM dbstat').fetchone()[0]
        except Exception: total = os.path.getsize(self.path)
        db.close(); return total
    def server_rss_kib(self): return 0


class GroupCommitSQLite(SQLite):
    """One writer thread: commands arriving within the window share one transaction and one fsync.
    Each command runs in its own SAVEPOINT, so a failing command rolls back alone; callers are answered only
    after COMMIT returns, so an acknowledged command is as durable as with one transaction per command."""
    def __init__(self, path, window_ms=2.0, max_batch=64):
        super().__init__(path, 'NORMAL'); self.window, self.max_batch = window_ms / 1000, max_batch
        self.q, self.batches, self.writer = queue.Queue(), [], None

    def start(self):
        self.writer = threading.Thread(target=self._loop, daemon=True); self.writer.start()

    def _collect(self, first):
        batch, deadline = [first], time.perf_counter() + self.window
        while len(batch) < self.max_batch:
            remaining = deadline - time.perf_counter()
            if remaining <= 0: break
            try: item = self.q.get(timeout=remaining)
            except queue.Empty: break
            if item is None: self.q.put(None); break
            batch.append(item)
        return batch

    def _loop(self):
        db = self.connect(); cur = db.cursor()
        while (first := self.q.get()) is not None:
            batch = self._collect(first)
            cur.execute('BEGIN IMMEDIATE')
            for request in batch:
                cur.execute('SAVEPOINT r')
                try: request['fn'](cur, self.ph, request['i']); cur.execute('RELEASE r')
                except Exception as error: cur.execute('ROLLBACK TO r'); cur.execute('RELEASE r'); request['error'] = error
            cur.execute('COMMIT'); self.batches.append(len(batch))
            for request in batch: request['done'].set()
        db.close()

    def run(self, db, fn, i, write):
        if not write: return SQLite.run(self, db, fn, i, write)  # queries keep their own NORMAL transaction
        request = {'fn': fn, 'i': i, 'error': None, 'done': threading.Event()}
        self.q.put(request); request['done'].wait()
        if request['error'] is not None: raise request['error']

    def stop(self): self.q.put(None); self.writer.join()


class Postgres:
    ph, blob = '%s', 'BYTEA'
    def __init__(self, dsn, pid_fn, shared_session=False):
        import psycopg
        self.psycopg, self.dsn, self.pid_fn, self.shared_session = psycopg, dsn, pid_fn, shared_session
    def connect(self):
        # PGlite multiplexes all clients onto one engine session: server-side prepared statements would collide.
        return self.psycopg.connect(self.dsn, autocommit=False, prepare_threshold=None if self.shared_session else 5)
    def setup(self):
        with self.connect() as db:
            for t in TABLES: db.execute(f'DROP TABLE IF EXISTS {t}')
            for s in DDL: db.execute(s.format(B=self.blob).replace('INTEGER PRIMARY KEY, stream', 'BIGSERIAL PRIMARY KEY, stream'))
            db.commit()
        with self.connect() as db:
            db.autocommit = True; db.execute('CHECKPOINT')
    def run(self, db, fn, i, write):
        with db.cursor() as cur:
            try: fn(cur, self.ph, i); db.commit()
            except BaseException: db.rollback(); raise
    def size(self):
        with self.connect() as db:
            return int(db.execute('SELECT sum(pg_total_relation_size(c)) FROM unnest(%s::regclass[]) c', (TABLES,)).fetchone()[0])
    def server_rss_kib(self): return self.pid_fn()


def rss_of(pids):
    total = 0
    for pid in pids:
        try:
            with open(f'/proc/{pid}/status') as f:
                for line in f:
                    if line.startswith('VmRSS:'): total += int(line.split()[1])
        except OSError: pass
    return total


def children(root):
    out = [root]
    try:
        for tid in os.listdir(f'/proc/{root}/task'):
            with open(f'/proc/{root}/task/{tid}/children') as f: out += [int(p) for p in f.read().split()]
    except OSError: pass
    return out


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--engine', required=True); a.add_argument('--clients', type=int, default=1); a.add_argument('--n', type=int, default=300)
    a.add_argument('--path'); a.add_argument('--dsn'); a.add_argument('--server-pid', type=int); a.add_argument('--window-ms', type=float, default=2.0)
    o = a.parse_args()
    server_pids = lambda: rss_of([q for p in children(o.server_pid) for q in children(p)]) if o.server_pid else 0
    if o.engine == 'sqlite': eng = SQLite(o.path)
    elif o.engine == 'sqlite-normal-reads': eng = SQLite(o.path, 'NORMAL')
    elif o.engine == 'sqlite-group': eng = GroupCommitSQLite(o.path, o.window_ms)
    else: eng = Postgres(o.dsn, server_pids, shared_session=o.engine == 'pglite')
    eng.setup()
    if isinstance(eng, GroupCommitSQLite): eng.start()
    writes, reads = [[] for _ in range(o.clients)], [[] for _ in range(o.clients)]
    peak_server = [0]; stop = threading.Event()
    def sample():
        while not stop.is_set(): peak_server[0] = max(peak_server[0], eng.server_rss_kib()); time.sleep(0.05)
    sampler = threading.Thread(target=sample, daemon=True); sampler.start()
    per = o.n // o.clients
    def client(c):
        db = eng.connect()
        for k in range(per):
            i = c * per + k; t = time.perf_counter(); eng.run(db, command, i, True); writes[c].append(time.perf_counter() - t)
        for k in range(per):
            i = c * per + k; t = time.perf_counter(); eng.run(db, query, i, False); reads[c].append(time.perf_counter() - t)
        db.close()
    cpu0 = time.process_time(); t0 = time.perf_counter()
    threads = [threading.Thread(target=client, args=(c,)) for c in range(o.clients)]
    for t in threads: t.start()
    for t in threads: t.join()
    elapsed = time.perf_counter() - t0; cpu = time.process_time() - cpu0
    stop.set(); sampler.join()
    if isinstance(eng, GroupCommitSQLite): eng.stop()
    w = [x for xs in writes for x in xs]; r = [x for xs in reads for x in xs]
    pct = lambda xs, q: sorted(xs)[min(len(xs) - 1, int(q * len(xs)))] * 1e6
    out = {'engine': o.engine, 'clients': o.clients, 'ops': len(w) + len(r),
           'write_p50_us': pct(w, .5), 'write_p95_us': pct(w, .95), 'read_p50_us': pct(r, .5), 'read_p95_us': pct(r, .95),
           'throughput_ops_s': (len(w) + len(r)) / elapsed, 'client_cpu_us_per_op': cpu / (len(w) + len(r)) * 1e6,
           'client_max_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'server_peak_rss_kib': peak_server[0],
           'logical_bytes_per_write': eng.size() / len(w)}
    if isinstance(eng, GroupCommitSQLite): out['mean_batch'] = statistics.mean(eng.batches) if eng.batches else 0
    print(json.dumps({k: (round(v, 1) if isinstance(v, float) else v) for k, v in out.items()}))


if __name__ == '__main__':
    main()
