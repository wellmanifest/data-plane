#!/usr/bin/env python3
"""Offline artifact conformance checks; does NOT certify a running system."""
import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path: sys.path.insert(0,str(HERE))
from generate_contracts import generate
from jsonschema import Draft202012Validator, FormatChecker
from graphql import build_schema, validate_schema
from pglast import parse_sql, parse_plpgsql

ROOT=HERE.parent
CHECKER=FormatChecker()
MAX_INT64=9223372036854775807

def load(path):
    return json.loads((ROOT/path).read_text())

def validate_instance(schema,value):
    Draft202012Validator(schema,format_checker=CHECKER).validate(value)

def semantic_checks(schema,value):
    if isinstance(value,dict):
        for key,sub in schema.get('properties',{}).items():
            if key in value: semantic_checks(sub,value[key])
    elif isinstance(value,list):
        for item in value: semantic_checks(schema.get('items',{}),item)
    elif schema.get('x-graphql-scalar')=='Base64':
        decoded=base64.b64decode(value,validate=True)
        if len(decoded)>32768: raise ValueError('Inline blob exceeds decoded byte limit')
        if base64.b64encode(decoded).decode()!=value: raise ValueError('Non-canonical base64')
    elif schema.get('x-graphql-scalar')=='Revision':
        if int(value)>MAX_INT64: raise ValueError('Decimal string exceeds PostgreSQL BIGINT')

def validate_command(operation,value):
    validate_instance(operation['inputSchema'],value)
    semantic_checks(operation['inputSchema'],value)

def validate_response(operation,value):
    validate_instance(operation['outputSchema'],value)
    semantic_checks(operation['outputSchema'],value)
    result=value['result']
    if operation['name']=='resource.read' and 'contentBase64' in result:
        raw=base64.b64decode(result['contentBase64'],validate=True)
        ref=result['resource']
        if hashlib.sha256(raw).hexdigest()!=ref['sha256'] or len(raw)!=int(ref['byteLength']):
            raise ValueError('Resource example integrity mismatch')

def run_checks():
    checks=[]
    def passed(name,**details): checks.append({'check':name,'status':'passed',**details})
    schema_files=sorted((ROOT/'schemas').glob('*.schema.json'))+[ROOT/'reference/process-exchange.schema.json']
    for path in schema_files: Draft202012Validator.check_schema(json.loads(path.read_text()))
    passed('json-schema-metaschema',files=len(schema_files))
    validate_instance(load('schemas/manifest.schema.json'),load('manifest.json'))
    validate_instance(load('schemas/migration-plan.schema.json'),load('examples/migration-plan.json'))
    passed('manifest-and-migration-example')
    catalog=load('contracts/operations.json'); ops=catalog['operations']
    names=set(); uris=set()
    for op in ops:
        if op['name'] in names or op['uri'] in uris: raise ValueError('Duplicate operation identity')
        names.add(op['name']); uris.add(op['uri'])
        if not re.fullmatch(r'process://[a-z0-9-]+/[a-z0-9._/-]+/v[1-9][0-9]*',op['uri']):
            raise ValueError('Invalid operation URI: '+op['uri'])
        if op['effects'] not in [['read'],['write'],['execute']]: raise ValueError('Invalid effects')
        if not op['scopes']: raise ValueError('Missing scopes')
        for name in ['inputSchema','outputSchema']: Draft202012Validator.check_schema(op[name])
        mutation=op['effects']!=['read']
        if mutation != ('idempotencyKey' in op['inputSchema']['required']): raise ValueError('Idempotency requirement mismatch')
        expected_root='Mutation' if mutation else 'Query'
        if op['transports']['graphql']['root']!=expected_root: raise ValueError('Wrong GraphQL root')
    passed('operation-catalog',operations=len(ops))
    generated=generate(catalog)
    for path,text in generated.items():
        if (ROOT/path).read_text()!=text: raise ValueError('Generated contract drift: '+path)
    passed('generated-transports-no-drift',files=len(generated))
    api=load('contracts/openapi.json')
    for path,spec in api['paths'].items():
        post=spec['post']
        refs=[post['requestBody']['content']['application/json']['schema']['$ref']]
        refs += [resp['content']['application/json']['schema']['$ref'] for resp in post['responses'].values()]
        for ref in refs:
            if ref.split('/')[-1] not in api['components']['schemas']: raise ValueError('Broken OpenAPI ref')
    passed('openapi-internal-references',paths=len(api['paths']),scope='Internal structure only; no HTTP runtime')
    gql=build_schema((ROOT/'contracts/schema.graphql').read_text())
    errors=validate_schema(gql)
    if errors: raise ValueError(str(errors))
    for op in ops:
        mapping=op['transports']['graphql']
        if mapping['field'] not in gql.get_type(mapping['root']).fields: raise ValueError('Missing GraphQL field')
    passed('graphql-sdl-and-operation-mapping')
    sql_files=list((ROOT/'examples/postgres').glob('*.sql'))
    statements=0
    for path in sql_files: statements+=len(parse_sql(path.read_text()))
    # PostgreSQL SQL parser treats function bodies as strings: validate PL/pgSQL too.
    functions=[]
    for path in sql_files:
        functions.extend(parse_plpgsql(path.read_text()))
    passed('postgresql-sql-and-plpgsql-syntax',files=len(sql_files),statements=statements,plpgsqlObjects=len(functions),scope='Parser only; no PostgreSQL server execution')
    mapping={'resource-read':'resource.read','resource-publish':'resource.publish','process-submit':'process.submit'}
    byname={op['name']:op for op in ops}; count=0
    for path in (ROOT/'examples/messages').glob('*.json'):
        stem,kind=path.name.removesuffix('.json').rsplit('.',1)
        value=json.loads(path.read_text()); op=byname[mapping[stem]]
        (validate_command if kind=='request' else validate_response)(op,value)
        count+=1
    passed('request-response-examples',files=count)
    jobs=load('examples/job-registry.json')['operations']
    request=load('examples/messages/process-submit.request.json')['arguments']
    job=next(j for j in jobs if j['uri']==request['operationUri'])
    validate_instance(job['inputSchema'],request['parameters'])
    passed('example-process-registry-second-stage-validation')
    sys.path.insert(0,str(ROOT))
    from conformance.event_store import decode_event
    raw=(ROOT/'examples/domain-event.json').read_bytes().removesuffix(b'\n')
    event=decode_event(raw)
    validate_instance(load('schemas/domain-event.schema.json'),event)
    if any(op.get('cqrs')!=('query' if op['effects']==['read'] else 'command') for op in ops):
        raise ValueError('CQRS declaration mismatch')
    if any(not op.get('poa',{}).get('required') for op in ops):raise ValueError('Missing POA')
    for profile in ['sqlite-embedded-es-v1','hybrid-sqlite-postgres-es-v1','postgres-es-v1']:
        if load('profiles/'+profile+'.json')['requiredArchitecture']!=['POA','CQRS','ES']:
            raise ValueError('Storage profile missing architecture invariants')
    passed('domain-fixture-and-required-poa-cqrs-es-profiles')
    return {'status':'passed','scope':'offline-artifacts-only','checks':checks,
            'notTested':['live-postgresql','live-redis','gateway-or-mcp-runtime','actual-user-sqlite-migration','performance','production-deployment']}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json-report',type=Path)
    args=parser.parse_args()
    result=run_checks()
    if args.json_report: args.json_report.write_text(json.dumps(result,indent=2)+'\n')
    for check in result['checks']: print('PASS '+check['check'])
    print('No live infrastructure or production migration tested.')

if __name__=='__main__': main()
