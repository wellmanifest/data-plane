#!/usr/bin/env python3
"""Validate fixtures with the exact upstream checker; never modify an existing checkout."""
import hashlib,importlib.util,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def check():
    lock=json.loads((ROOT/'upstream.lock.json').read_text())
    configured=os.environ.get('WELLLOGS_ROOT')
    checkout=Path(configured).resolve() if configured else ROOT/'build/upstream-logs'
    if not checkout.exists():
        if configured:raise RuntimeError('WELLLOGS_ROOT does not exist')
        checkout.mkdir(parents=True)
        subprocess.run(['git','init','-q',str(checkout)],check=True)
        subprocess.run(['git','-C',str(checkout),'remote','add','origin',lock['repository']],check=True)
        subprocess.run(['git','-C',str(checkout),'fetch','--quiet','--depth','1','origin',lock['commit']],check=True)
        subprocess.run(['git','-C',str(checkout),'checkout','--quiet','--detach','FETCH_HEAD'],check=True)
    head=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()
    if head!=lock['commit']:raise RuntimeError('Upstream commit mismatch; existing checkout left unchanged')
    for path,sha in lock['files'].items():
        if hashlib.sha256((checkout/path).read_bytes()).hexdigest()!=sha:raise RuntimeError('Upstream digest mismatch: '+path)
    spec=importlib.util.spec_from_file_location('pinned_wellmanifest_logs',checkout/'standard/logs_check.py')
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    result=mod.validate_repository(checkout)
    if not result['valid']:raise RuntimeError('Pinned upstream fixture validation failed: '+json.dumps(result))
    bundle,sha=mod.load_contract(checkout);catalog=mod.load_error_catalog(checkout,bundle)
    previous='0'*64;prior={};count=0
    with (ROOT/'examples/logs-audit.jsonl').open('rb') as source:
        for number,line in enumerate(source,1):
            if len(line)>65536:raise RuntimeError('Audit fixture exceeds line bound')
            event=json.loads(line)
            if mod.canonical(event).encode()+b'\n'!=line:raise RuntimeError('Audit bytes not canonical')
            previous=mod.validate_event(event,bundle=bundle,catalog=catalog,root=ROOT,
                path=f'examples/logs-audit.jsonl:{number}',stream='data-plane-fixture',sequence=number,previous_hash=previous,prior_events=prior)
            if event['eventId'] in prior:raise RuntimeError('Duplicate audit event')
            prior[event['eventId']]=event;count+=1
    errors=mod.validate_adopted_error_catalog(checkout,ROOT/'logs-error-catalog.v1.json')
    if not errors['valid']:raise RuntimeError('Adopter error catalog failed: '+json.dumps(errors))
    return {'status':'passed','upstreamCommit':head,'contractSha256':sha,'upstreamValidation':result,'ourErrorCatalogValidation':errors,'ourAuditFixturesValidated':count,
            'scope':'pinned-upstream-and-synthetic-audit-fixture','runtimeAdoptionProven':False}

if __name__=='__main__':print(json.dumps(check(),indent=2))
