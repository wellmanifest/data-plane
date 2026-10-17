#!/usr/bin/env python3
"""Read-only SQLite inventory using a consistent temporary Backup API snapshot."""
import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path

def quote_identifier(value):
    if '\x00' in value:
        raise ValueError('NUL in identifier')
    return '"'+value.replace('"','""')+'"'

def file_hash(path):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()

def _inspect_column_storage_types(con, q, col_name):
    qc=quote_identifier(col_name)
    rows=con.execute(f'SELECT typeof({qc}) AS storage_type, COUNT(*) AS n FROM {q} GROUP BY typeof({qc})').fetchall()
    return {r['storage_type']:r['n'] for r in rows}

def _inspect_table(con, name, ddl, check_deadline):
    table={'name':name,'ddl':ddl}
    try:
        q=quote_identifier(name)
        cols=con.execute(f'PRAGMA table_xinfo({q})').fetchall()
        fks=con.execute(f'PRAGMA foreign_key_list({q})').fetchall()
        idxs=con.execute(f'PRAGMA index_list({q})').fetchall()
        table['columns']=[dict(r) for r in cols]
        table['foreignKeys']=[dict(r) for r in fks]
        table['indexes']=[dict(r) for r in idxs]
        table['rowCount']=con.execute(f'SELECT COUNT(*) FROM {q}').fetchone()[0]
        table['storageTypes']={}
        for col in table['columns']:
            table['storageTypes'][col['name']]=_inspect_column_storage_types(con, q, col['name'])
    except sqlite3.DatabaseError:
        check_deadline()
        table['scanError']='SQLite scan failed; required extension, view dependency or schema may be unavailable'
        return table, False
    return table, True

def audit(path, timeout=300):
    path=Path(path).resolve(strict=True)
    if not path.is_file(): raise ValueError('Source is not a regular file')
    if timeout<=0: raise ValueError('timeout must be positive')
    deadline=time.monotonic()+timeout
    def check_deadline(*_):
        if time.monotonic()>deadline: raise TimeoutError('SQLite audit deadline exceeded')
    report={'schema':'data-plane.sqlite-audit/v1','sqliteVersion':sqlite3.sqlite_version,
            'sourceFile':path.name,'readOnlySource':True,'snapshotMethod':'sqlite-backup-api',
            'tables':[],'views':[],'triggers':[],'warnings':[], 'complete':True}
    with tempfile.TemporaryDirectory(prefix='data-plane-sqlite-audit-') as temp:
        snapshot=Path(temp)/'snapshot.sqlite'
        # mkstemp directory permissions protect snapshot; SQLite source opened read-only.
        source=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=min(timeout,5))
        target=sqlite3.connect(snapshot)
        try:
            source.execute('PRAGMA query_only=ON')
            source.backup(target,pages=128,progress=check_deadline,sleep=0.01)
        finally:
            target.close(); source.close()
        report['snapshotSha256']=file_hash(snapshot)
        con=sqlite3.connect(snapshot.as_uri()+'?mode=ro',uri=True)
        try:
            con.row_factory=sqlite3.Row
            con.execute('PRAGMA query_only=ON')
            con.set_progress_handler(lambda: int(time.monotonic()>deadline),10000)
            integrity_rows=con.execute('PRAGMA integrity_check').fetchall()
            integrity=[row[0] for row in integrity_rows]
            # Integrity diagnostics can mention values. Report counts, not row content.
            report['integrity']={'ok':integrity==['ok'],'diagnosticCount':0 if integrity==['ok'] else len(integrity)}
            try:
                fk_rows=con.execute('PRAGMA foreign_key_check').fetchall()
                report['foreignKeyViolationCount']=len(fk_rows)
            except sqlite3.DatabaseError:
                report['foreignKeyViolationCount']=None
                report['complete']=False
                report['warnings'].append('foreign_key_check failed; inspect schema on a controlled copy')
            report['userVersion']=con.execute('PRAGMA user_version').fetchone()[0]
            objects=con.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
            for entry in objects:
                check_deadline()
                typ,name=entry['type'],entry['name']
                if typ=='view': report['views'].append(dict(entry)); continue
                if typ=='trigger': report['triggers'].append(dict(entry)); continue
                if typ!='table': continue
                table, ok=_inspect_table(con, name, entry['sql'], check_deadline)
                if not ok:
                    report['complete']=False
                report['tables'].append(table)
        finally:
            con.close()
    report['migrationReady']=False
    report['readinessNote']='Inventory only. Semantic mapping, data reconciliation, restore and application tests are still required.'
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--timeout',type=float,default=300)
    args=parser.parse_args()
    try:
        source=args.database.resolve(strict=True)
        output=args.output.resolve()
        # Never overwrite a DB, a sidecar or an existing report accidentally.
        if output==source or str(output) in {str(source)+s for s in ['-wal','-shm','-journal']}:
            raise ValueError('Output conflicts with SQLite source or sidecar')
        if output.exists(): raise ValueError('Output already exists; choose a new report path')
        result=audit(source,args.timeout)
        fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(result,f,ensure_ascii=False,indent=2); f.write('\n')
        print(f'Wrote audit report: {output}')
        return 0 if result['complete'] and result['integrity']['ok'] and result['foreignKeyViolationCount']==0 else 2
    except (OSError,ValueError,TimeoutError,sqlite3.DatabaseError) as exc:
        # SQLite error messages can contain data or arbitrary identifiers.
        if isinstance(exc,sqlite3.DatabaseError):
            raise SystemExit('Audit failed: SQLite database error; inspect a controlled copy') from None
        raise SystemExit(f'Audit failed: {exc}') from None

if __name__=='__main__':
    raise SystemExit(main())
