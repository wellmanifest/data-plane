"""Live PostgreSQL 16 checks of examples/postgres/es-schema.sql (skipped unless DATA_PLANE_PG_DSN is set).

DATA_PLANE_PG_DSN must reach a disposable server as a role that may CREATE DATABASE and CREATE ROLE.
Each run creates and drops its own database; nothing else on the server is touched.
"""
import os
import pathlib
import unittest
import uuid

DSN = os.environ.get('DATA_PLANE_PG_DSN')
try:
    import psycopg
    from psycopg import errors, sql
except ImportError:  # the static suite does not need a driver
    psycopg = None

ROOT = pathlib.Path(__file__).resolve().parents[1]
H = '0' * 64


@unittest.skipUnless(DSN and psycopg, 'set DATA_PLANE_PG_DSN (and install psycopg) to run live PostgreSQL checks')
class PostgresEventStoreLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = 'dp_live_' + uuid.uuid4().hex[:12]
        cls.role = 'dp_app_' + uuid.uuid4().hex[:8]
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
            admin.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(cls.role)))
        cls.dsn = psycopg.conninfo.make_conninfo(DSN, dbname=cls.database)
        with psycopg.connect(cls.dsn, autocommit=True) as db:
            db.execute((ROOT / 'examples/postgres/es-schema.sql').read_text())
            # The reference schema creates no production roles; grant a plain application role for RLS checks.
            db.execute(sql.SQL('GRANT USAGE ON SCHEMA data_plane_es TO {r}; GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA data_plane_es TO {r}')
                       .format(r=sql.Identifier(cls.role)))

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(cls.database)))
            admin.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(cls.role)))

    def app(self, tenant):
        db = psycopg.connect(self.dsn)
        db.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(self.role)))
        if tenant is not None:
            db.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant),))
        return db

    def append(self, db, tenant, stream, version=1):
        if version == 1:
            db.execute('INSERT INTO data_plane_es.stream_heads VALUES (%s,%s,%s,1,0,%s) ON CONFLICT DO NOTHING',
                       (tenant, stream, 'authority:test', H))
        event_id = uuid.uuid4()
        db.execute('INSERT INTO data_plane_es.domain_events VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,NULL,now(),%s,1,%s,%s,%s,%s,%s)',
                   (event_id, tenant, stream, version, 'counter.changed', 'process://data-gateway/counter.change/v2',
                    uuid.uuid4(), uuid.uuid4(), 'authority:test', H, H, H, H, b'{}'))
        return event_id

    def test_tenants_are_isolated_by_row_level_security(self):
        a, b, stream = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        with self.app(a) as db:
            self.append(db, a, stream); db.commit()
            self.assertEqual(db.execute('SELECT count(*) FROM data_plane_es.domain_events WHERE stream_id=%s', (stream,)).fetchone()[0], 1)
        with self.app(b) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM data_plane_es.domain_events WHERE stream_id=%s', (stream,)).fetchone()[0], 0)
            with self.assertRaises(errors.InsufficientPrivilege):  # WITH CHECK rejects writing another tenant's row
                self.append(db, a, uuid.uuid4())
        with self.app(None) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM data_plane_es.stream_heads').fetchone()[0], 0)

    def test_history_is_immutable(self):
        tenant, stream = uuid.uuid4(), uuid.uuid4()
        with self.app(tenant) as db:
            event_id = self.append(db, tenant, stream); db.commit()
            for statement in ('UPDATE data_plane_es.domain_events SET event_type=%s WHERE event_id=%s',
                              'DELETE FROM data_plane_es.domain_events WHERE event_id=%s AND event_type<>%s'):
                params = ('x', event_id) if statement.startswith('UPDATE') else (event_id, 'x')
                with self.assertRaises(errors.IntegrityConstraintViolation):
                    db.execute(statement, params)
                db.rollback()

    def test_stream_versions_are_unique_and_head_cas_is_guarded(self):
        tenant, stream = uuid.uuid4(), uuid.uuid4()
        with self.app(tenant) as db:
            self.append(db, tenant, stream); db.commit()
            with self.assertRaises(errors.UniqueViolation):
                self.append(db, tenant, stream, version=1)
            db.rollback()
            guarded = ('UPDATE data_plane_es.stream_heads SET stream_version=%s, event_hash=%s '
                       'WHERE tenant_id=%s AND stream_id=%s AND authority_id=%s AND authority_epoch=1 AND stream_version=%s')
            self.assertEqual(db.execute(guarded, (2, H, tenant, stream, 'authority:test', 5)).rowcount, 0)  # stale expectation
            self.assertEqual(db.execute(guarded, (1, H, tenant, stream, 'authority:test', 0)).rowcount, 1)
            db.commit()


if __name__ == '__main__':
    unittest.main()
