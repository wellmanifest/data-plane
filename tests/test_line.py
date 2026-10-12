import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from conformance.line import (LineError,classify,error_codes,error_to_line,event_to_line,format_line,line_hash,line_to_error,
    line_to_event,line_to_request,line_to_response,load_contracts,parse,request_to_line,response_to_line)
from jsonschema import Draft202012Validator,FormatChecker

CONTRACTS=load_contracts()
BINDINGS,OPERATIONS=CONTRACTS
READ='resource.read: urn:uuid:11111111-1111-4111-8111-111111111111 {"consistency":"strong","requestId":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}'

def load(path): return json.loads((ROOT/path).read_text())

class LineGrammar(unittest.TestCase):
    def test_canonical_form_and_hash_ignore_json_whitespace_and_key_order(self):
        loose='resource.read: urn:uuid:11111111-1111-4111-8111-111111111111 { "requestId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "consistency": "strong" }\r\n'
        self.assertEqual(format_line(*parse(loose)),READ)
        self.assertEqual(line_hash(loose),line_hash(READ))
        self.assertEqual(parse(READ,strict=True)[0],'resource.read')
        with self.assertRaisesRegex(LineError,'not canonical'):parse(loose,strict=True)

    def test_empty_variables_are_omitted(self):
        self.assertEqual(format_line('process.status','urn:uuid:11111111-1111-4111-8111-111111111111',{}),
                         'process.status: urn:uuid:11111111-1111-4111-8111-111111111111')
        self.assertEqual(parse('process.status: urn:uuid:11111111-1111-4111-8111-111111111111 {}')[2],{})

    def test_malformed_lines_are_rejected(self):
        cases={
            'missing colon':'resource.read urn:uuid:1',
            'uppercase type':'Resource.Read: urn:uuid:1',
            'no space after colon':'resource.read:urn:uuid:1',
            'relative target':'resource.read: /v2/resources/1',
            'whitespace in target':'resource.read: urn:uuid:1 2',
            'non-ascii target':'resource.read: urn:x:zażółć',
            'json array':'resource.read: urn:uuid:1 [1]',
            'invalid json':'resource.read: urn:uuid:1 {"a":}',
            'duplicate key':'resource.read: urn:uuid:1 {"a":1,"a":2}',
            'float':'resource.read: urn:uuid:1 {"a":1.5}',
            'unsafe integer':'resource.read: urn:uuid:1 {"a":9007199254740993}',
            'nan':'resource.read: urn:uuid:1 {"a":NaN}',
            'embedded newline':'resource.read: urn:uuid:1 {"a":1}\nprocess.cancel: urn:uuid:2',
            'trailing space':'resource.read: urn:uuid:1 ',
            'bom':'﻿resource.read: urn:uuid:1',
            'too deep':'resource.read: urn:uuid:1 '+'{"a":'*40+'1'+'}'*40,
            'too long':'resource.read: urn:uuid:1 {"a":"'+'x'*70000+'"}',
        }
        for name,line in cases.items():
            with self.subTest(name),self.assertRaises(LineError):parse(line)

    def test_parsed_form_matches_schema(self):
        validator=Draft202012Validator(load('schemas/line.schema.json'))
        kind,target,variables=parse(READ)
        validator.validate({'type':kind,'target':target,'vars':variables})

class OperationBindings(unittest.TestCase):
    def test_every_operation_has_a_safe_binding(self):
        self.assertEqual(set(BINDINGS['bindings']),set(OPERATIONS))
        for name,operation in OPERATIONS.items():
            arguments=operation['inputSchema']['properties']['arguments']
            control={key for key in operation['inputSchema']['properties'] if key!='arguments'}
            with self.subTest(name):
                self.assertFalse(control&set(arguments['properties']),'argument shadows a control field')
                binding=BINDINGS['bindings'][name]
                if binding['target']=='argument':
                    self.assertIn(binding['argument'],arguments['required'])

    def test_request_messages_round_trip_through_lines(self):
        for path in sorted((ROOT/'examples/messages').glob('*.request.json')):
            name=path.name.removesuffix('.request.json').replace('-','.')
            envelope=json.loads(path.read_text())
            with self.subTest(name):
                line=request_to_line(name,envelope,CONTRACTS)
                self.assertTrue(line.startswith(name+': '))
                self.assertEqual(line_to_request(line,CONTRACTS),(name,envelope))
                self.assertEqual(classify(line,CONTRACTS),'request')
                Draft202012Validator(OPERATIONS[name]['inputSchema'],format_checker=FormatChecker()).validate(envelope)

    def test_uuid_form_and_operation_targets_are_enforced(self):
        envelope={'requestId':'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','arguments':{'entityId':'22222222-2222-4222-8222-222222222222'}}
        line=request_to_line('entity.resolve',envelope,CONTRACTS)
        self.assertIn('entity.resolve: urn:uuid:22222222-2222-4222-8222-222222222222 ',line)
        self.assertEqual(line_to_request(line,CONTRACTS)[1],envelope)
        with self.assertRaisesRegex(LineError,'urn:uuid'):
            line_to_request('entity.resolve: urn:isbn:0451450523',CONTRACTS)
        with self.assertRaisesRegex(LineError,'operation URI'):
            line_to_request('dataset.query: process://elsewhere/dataset.query/v2 {"queryId":"q"}',CONTRACTS)
        with self.assertRaisesRegex(LineError,'given twice'):
            line_to_request(READ[:-1]+',"urn":"urn:uuid:22222222-2222-4222-8222-222222222222"}',CONTRACTS)

    def test_responses_round_trip(self):
        for path in sorted((ROOT/'examples/messages').glob('*.response.json')):
            output=json.loads(path.read_text())
            with self.subTest(path.name):
                line=response_to_line(output)
                self.assertTrue(line.startswith('result: urn:uuid:'+output['requestId']))
                self.assertEqual(line_to_response(line),output)

class ErrorLines(unittest.TestCase):
    REQUEST='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'

    def test_catalog_error_round_trips(self):
        line=error_to_line(self.REQUEST,'DP-CONCURRENCY-001',retryable=True,message='Expected version is stale.')
        self.assertEqual(line,'error: urn:uuid:'+self.REQUEST+' {"code":"DP-CONCURRENCY-001","message":"Expected version is stale.","retryable":true}')
        self.assertEqual(line_to_error(line),{'requestId':self.REQUEST,'code':'DP-CONCURRENCY-001','message':'Expected version is stale.','retryable':True})
        self.assertEqual(classify(line,CONTRACTS),'error')

    def test_every_catalog_code_has_a_runbook_and_is_accepted(self):
        for code in error_codes():
            with self.subTest(code):
                self.assertTrue((ROOT/'errors'/f'{code}.md').exists())
                line_to_error(error_to_line(self.REQUEST,code))

    def test_error_lines_are_closed(self):
        cases={
            'unknown code':'error: urn:uuid:'+self.REQUEST+' {"code":"LOGS-VALIDATION-001"}',
            'missing code':'error: urn:uuid:'+self.REQUEST+' {"message":"x"}',
            'echoed request variables':'error: urn:uuid:'+self.REQUEST+' {"code":"DP-SOURCE-001","request":{"token":"x"}}',
            'non-boolean retryable':'error: urn:uuid:'+self.REQUEST+' {"code":"DP-SOURCE-001","retryable":"yes"}',
            'long message':'error: urn:uuid:'+self.REQUEST+' {"code":"DP-SOURCE-001","message":"'+'x'*513+'"}',
            'not a request target':'error: process://data-gateway/resource.read/v2 {"code":"DP-SOURCE-001"}',
        }
        for name,line in cases.items():
            with self.subTest(name),self.assertRaises(LineError):line_to_error(line)

class EventProjections(unittest.TestCase):
    def test_audit_and_domain_events_project_losslessly(self):
        events=[json.loads(line) for line in (ROOT/'examples/logs-audit.jsonl').read_text().splitlines()]
        events.append(load('examples/domain-event.json'))
        for event in events:
            with self.subTest(event['schema']):
                line=event_to_line(event,CONTRACTS)
                self.assertEqual(line_to_event(line,CONTRACTS),event)
                self.assertEqual(classify(line,CONTRACTS),event['schema'])

    def test_unprojectable_events_fail_closed(self):
        event=json.loads((ROOT/'examples/logs-audit.jsonl').read_text().splitlines()[0])
        with self.assertRaisesRegex(LineError,'addressable target'):
            event_to_line({**event,'subjectRef':None},CONTRACTS)
        with self.assertRaisesRegex(LineError,'no declared line projection'):
            event_to_line({**event,'schema':'other/v1'},CONTRACTS)

class Compatibility(unittest.TestCase):
    def test_nl_uri_hybrid_line_is_a_valid_line(self):
        line='uri: sandbox://run {"image": "python:3.11-slim", "cmd": "pytest tests/ -q"}'
        self.assertEqual(classify(line,CONTRACTS),'uri')
        self.assertEqual(parse(line)[2],{'image':'python:3.11-slim','cmd':'pytest tests/ -q'})

    def test_unknown_type_is_rejected(self):
        with self.assertRaisesRegex(LineError,'Unknown line type'):classify('shell.exec: urn:uuid:1 {"cmd":"rm"}',CONTRACTS)

    def test_published_examples_are_canonical_and_reproducible(self):
        lines=(ROOT/'examples/lines/examples.line').read_text().splitlines()
        for line in lines:
            with self.subTest(line[:40]):
                parse(line,strict=True);classify(line,CONTRACTS)
        expected=[request_to_line(p.name.removesuffix('.request.json').replace('-','.'),load(f'examples/messages/{p.name}'),CONTRACTS)
                  for p in [ROOT/'examples/messages'/f'{n}.request.json' for n in ('resource-read','process-submit','resource-publish')]]
        self.assertEqual(lines[:3],expected)

class ShellAdapter(unittest.TestCase):
    def run_cli(self,*args,stdin=''):
        return subprocess.run([sys.executable,str(ROOT/'tools/dp_line.py'),*args],input=stdin,capture_output=True,text=True)

    def test_cli_converts_and_fails_closed_without_echoing_payload(self):
        done=self.run_cli('to-request',READ)
        self.assertEqual(done.returncode,0)
        self.assertEqual(json.loads(done.stdout)['uri'],'process://data-gateway/resource.read/v2')
        secret='resource.read: urn:uuid:11111111-1111-4111-8111-111111111111 {"requestId":"not-a-uuid","token":"s3cr3t-value"}'
        done=self.run_cli('to-request',secret)
        self.assertEqual(done.returncode,2)
        self.assertNotIn('s3cr3t-value',done.stderr+done.stdout)

    def test_cli_checks_every_stdin_line(self):
        done=self.run_cli('check',stdin=(ROOT/'examples/lines/examples.line').read_text())
        self.assertEqual(done.returncode,0,done.stderr)
        done=self.run_cli('check',stdin=READ+'\nbroken line\n')
        self.assertEqual(done.returncode,2)
        self.assertEqual(json.loads(done.stderr)['line'],2)

if __name__=='__main__':
    unittest.main()
