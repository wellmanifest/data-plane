import base64
import copy
import json
from pathlib import Path
import sys
import unittest
from jsonschema import ValidationError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from validate import validate_command, validate_response, run_checks

OPS={op['name']:op for op in json.loads((ROOT/'contracts/operations.json').read_text())['operations']}
REQUEST_ID='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
URN='urn:uuid:11111111-1111-4111-8111-111111111111'

class Contracts(unittest.TestCase):
    def test_full_static_conformance(self):
        self.assertEqual(run_checks()['status'],'passed')

    def test_unknown_fields_and_tenant_spoof_rejected(self):
        value={'requestId':REQUEST_ID,'arguments':{'urn':URN},'tenantId':REQUEST_ID}
        with self.assertRaises(ValidationError): validate_command(OPS['resource.read'],value)

    def test_mutation_requires_idempotency(self):
        value={'requestId':REQUEST_ID,'arguments':{'processUrn':URN}}
        with self.assertRaises(ValidationError): validate_command(OPS['process.cancel'],value)

    def test_legacy_and_noncanonical_urn_rejected(self):
        for urn in ['urn:custom:123','urn:uuid:AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA',URN+'?x=1']:
            with self.subTest(urn=urn), self.assertRaises(ValidationError):
                validate_command(OPS['resource.read'],{'requestId':REQUEST_ID,'arguments':{'urn':urn}})

    def test_query_limit_bounded(self):
        with self.assertRaises(ValidationError):
            validate_command(OPS['dataset.query'],{'requestId':REQUEST_ID,'arguments':{'queryId':'jobs','parameters':{},'limit':201}})

    def test_revision_decimal_precision(self):
        value={'requestId':REQUEST_ID,'idempotencyKey':'x','arguments':{'entityId':REQUEST_ID,'resourceUrn':URN,'expectedRevision':'9223372036854775808'}}
        with self.assertRaises(ValueError): validate_command(OPS['entity.advance'],value)
        value['arguments']['expectedRevision']='9007199254740993'
        validate_command(OPS['entity.advance'],value)

    def test_base64_size_and_validity(self):
        value={'requestId':REQUEST_ID,'idempotencyKey':'x','arguments':{'mediaType':'application/octet-stream','contentBase64':'!!!!'}}
        with self.assertRaises(ValueError): validate_command(OPS['resource.publish'],value)
        value['arguments']['contentBase64']=base64.b64encode(b'x'*32769).decode()
        with self.assertRaises(ValueError): validate_command(OPS['resource.publish'],value)

    def test_succeeded_requires_verification(self):
        value={'requestId':REQUEST_ID,'replayed':False,'result':{'processUrn':URN,'state':'succeeded','cancelRequested':False,'outputs':[]}}
        with self.assertRaises(ValidationError): validate_response(OPS['process.status'],value)

    def test_resource_hash_integrity(self):
        value=json.loads((ROOT/'examples/messages/resource-read.response.json').read_text())
        value['result']['resource']['sha256']='0'*64
        with self.assertRaises(ValueError): validate_response(OPS['resource.read'],value)

if __name__=='__main__': unittest.main()
