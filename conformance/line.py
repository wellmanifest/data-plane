"""data-plane.line/v1: one line `type: target {vars}` for requests, results and event projections.

Reference parser and lossless mappings only. A line is data: parsing or converting it never grants
execution authority, and an audit projection never replaces the canonical wellmanifest/logs JSONL bytes.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

from conformance.event_store import canonical

ROOT=Path(__file__).resolve().parents[1]
MAX_LINE_BYTES=65536
MAX_TYPE_CHARS=128
MAX_TARGET_CHARS=2048
MAX_DEPTH=32
TYPE=re.compile(r'[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)*')
# Absolute RFC 3986 URI or RFC 8141 URN; non-ASCII must be percent-encoded, so whitespace cannot occur.
TARGET=re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+")
RESPONSE_TYPES={'result','error'}
URI_TYPE='uri'  # wellmanifest/nl-uri-dsl-llm hybrid line `uri: scheme://domain/action {...}`
UUID_URN='urn:uuid:'

class LineError(ValueError): pass

def _no_duplicates(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise LineError('Duplicate JSON key')
        result[key]=value
    return result

def _reject_constant(value): raise LineError('Non-finite JSON number')

def _depth(value,level=1):
    if level>MAX_DEPTH: raise LineError('JSON nesting exceeds bound')
    children=value.values() if isinstance(value,dict) else value if isinstance(value,list) else ()
    for child in children: _depth(child,level+1)

def parse(text,*,strict=False):
    """Return (type, target, vars). strict requires the canonical bytes used for hashing and logs."""
    raw=text.encode('utf-8') if isinstance(text,str) else bytes(text)
    if raw.endswith(b'\r\n'): raw=raw[:-2]
    elif raw.endswith(b'\n'): raw=raw[:-1]
    if len(raw)>MAX_LINE_BYTES: raise LineError('Line exceeds byte bound')
    if b'\n' in raw or b'\r' in raw: raise LineError('A line cannot contain a line break')
    try: line=raw.decode('utf-8')
    except UnicodeDecodeError: raise LineError('Line is not UTF-8') from None
    if line.startswith('﻿'): raise LineError('Byte order mark is not allowed')
    head,sep,rest=line.partition(': ')
    if not sep or not TYPE.fullmatch(head) or len(head)>MAX_TYPE_CHARS: raise LineError('Expected `type: target`')
    target,space,payload=rest.partition(' ')
    if not TARGET.fullmatch(target) or len(target)>MAX_TARGET_CHARS: raise LineError('Target must be an absolute URI or URN')
    if space and not payload.startswith('{'): raise LineError('Variables must be one JSON object')
    variables={}
    if space:
        try: variables=json.loads(payload,object_pairs_hook=_no_duplicates,parse_constant=_reject_constant)
        except LineError: raise
        except ValueError: raise LineError('Variables are not valid JSON') from None
        if not isinstance(variables,dict): raise LineError('Variables must be one JSON object')
        _depth(variables)
    try: canonical(variables)
    except ValueError as error: raise LineError(str(error)) from None
    if strict and format_line(head,target,variables)!=line: raise LineError('Line is not canonical')
    return head,target,variables

def format_line(kind,target,variables=None):
    """Canonical form: one space after the colon, sorted compact JSON, `{}` omitted."""
    if not TYPE.fullmatch(kind) or len(kind)>MAX_TYPE_CHARS: raise LineError('Invalid type')
    if not TARGET.fullmatch(target) or len(target)>MAX_TARGET_CHARS: raise LineError('Invalid target')
    variables=variables or {}
    if not isinstance(variables,dict): raise LineError('Variables must be one JSON object')
    _depth(variables)
    try: body=canonical(variables).decode('utf-8')
    except ValueError as error: raise LineError(str(error)) from None
    line=f'{kind}: {target}'+(' '+body if variables else '')
    if len(line.encode('utf-8'))>MAX_LINE_BYTES: raise LineError('Line exceeds byte bound')
    return line

def line_hash(text):
    """SHA-256 of the canonical line without LF; usable as wellmanifest/logs inputHash."""
    return hashlib.sha256(format_line(*parse(text)).encode('utf-8')).hexdigest()

def load_contracts(root=ROOT):
    bindings=json.loads((root/'contracts/line-bindings.json').read_text())
    catalog=json.loads((root/'contracts/operations.json').read_text())
    operations={op['name']:op for op in catalog['operations']}
    if set(operations)!=set(bindings['bindings']): raise LineError('Every catalog operation needs exactly one line binding')
    return bindings,operations

def classify(text,contracts=None):
    kind,target,variables=parse(text)
    bindings,operations=contracts or load_contracts()
    if variables.get('schema') in bindings['events']: return variables['schema']
    if kind==URI_TYPE: return 'uri'
    if kind in RESPONSE_TYPES: return kind
    if kind in operations: return 'request'
    raise LineError('Unknown line type')

def _control_fields(operation):
    return [name for name in operation['inputSchema']['properties'] if name!='arguments']

def request_to_line(name,envelope,contracts=None):
    bindings,operations=contracts or load_contracts()
    if name not in operations: raise LineError('Unknown operation')
    operation,binding=operations[name],bindings['bindings'][name]
    arguments=dict(envelope.get('arguments',{}))
    variables={key:value for key,value in envelope.items() if key!='arguments'}
    if binding['target']=='operation': target=operation['uri']
    else:
        value=arguments.pop(binding['argument'],None)
        if not isinstance(value,str): raise LineError('Target argument is missing')
        target=UUID_URN+value if binding.get('form')=='urn:uuid' else value
    if set(variables)&set(arguments): raise LineError('Argument name collides with a control field')
    variables.update(arguments)
    return format_line(name,target,variables)

def line_to_request(text,contracts=None,*,parsed=None):
    """Return (operationName, envelope) in the existing /v2 input shape; schema validation stays with the caller.
    `parsed` is this text's own parse() result, so a caller that already parsed the line does not parse it again."""
    bindings,operations=contracts or load_contracts()
    name,target,variables=parsed if parsed is not None else parse(text)
    if name not in operations: raise LineError('Line type is not a catalog operation')
    operation,binding=operations[name],bindings['bindings'][name]
    control=_control_fields(operation)
    envelope={key:variables[key] for key in control if key in variables}
    arguments={key:value for key,value in variables.items() if key not in control}
    if binding['target']=='operation':
        if target!=operation['uri']: raise LineError('Target must be the operation URI')
    else:
        if binding['argument'] in arguments: raise LineError('Target argument is given twice')
        if binding.get('form')=='urn:uuid':
            if not target.startswith(UUID_URN): raise LineError('Target must be a urn:uuid')
            target=target[len(UUID_URN):]
        arguments[binding['argument']]=target
    envelope['arguments']=arguments
    return name,envelope

def response_to_line(output):
    """`result: urn:uuid:<requestId> {...}` for an existing /v2 output envelope."""
    variables={key:value for key,value in output.items() if key!='requestId'}
    return format_line('result',UUID_URN+output['requestId'],variables)

def line_to_response(text):
    kind,target,variables=parse(text)
    if kind!='result' or not target.startswith(UUID_URN): raise LineError('Expected `result: urn:uuid:<requestId>`')
    return {'requestId':target[len(UUID_URN):],**variables}

ERROR_FIELDS={'code','retryable','message'}
MAX_ERROR_MESSAGE=512

def error_codes(root=ROOT):
    return set(json.loads((root/'logs-error-catalog.v1.json').read_text())['diagnosticCodes'])

def _check_error(variables,codes):
    if set(variables)-ERROR_FIELDS or 'code' not in variables: raise LineError('Error variables are code, retryable and message only')
    if variables['code'] not in codes: raise LineError('Error code is not in the adopter catalog')
    if 'retryable' in variables and not isinstance(variables['retryable'],bool): raise LineError('retryable must be boolean')
    message=variables.get('message','')
    if not isinstance(message,str) or len(message)>MAX_ERROR_MESSAGE: raise LineError('message must be a short string')

def error_to_line(request_id,code,*,retryable=None,message=None,codes=None):
    """`error: urn:uuid:<requestId> {"code":...}`; closed fields, catalog code, never the request variables."""
    variables={'code':code}
    if retryable is not None: variables['retryable']=retryable
    if message is not None: variables['message']=message
    _check_error(variables,codes if codes is not None else error_codes())
    return format_line('error',UUID_URN+request_id,variables)

def line_to_error(text,codes=None):
    kind,target,variables=parse(text)
    if kind!='error' or not target.startswith(UUID_URN): raise LineError('Expected `error: urn:uuid:<requestId>`')
    _check_error(variables,codes if codes is not None else error_codes())
    return {'requestId':target[len(UUID_URN):],**variables}

def event_to_line(event,contracts=None):
    """Lossless projection of a domain or audit event; the canonical event bytes stay authoritative."""
    bindings,_=contracts or load_contracts()
    projection=bindings['events'].get(event.get('schema'))
    if projection is None: raise LineError('Event schema has no declared line projection')
    kind,target=event.get(projection['type']),event.get(projection['target'])
    if not isinstance(target,str): raise LineError('Event has no addressable target')
    variables={key:value for key,value in event.items() if key not in (projection['type'],projection['target'])}
    return format_line(kind,target,variables)

def line_to_event(text,contracts=None):
    bindings,_=contracts or load_contracts()
    kind,target,variables=parse(text)
    projection=bindings['events'].get(variables.get('schema'))
    if projection is None: raise LineError('Line is not an event projection')
    if projection['type'] in variables or projection['target'] in variables: raise LineError('Projected field is given twice')
    return {**variables,projection['type']:kind,projection['target']:target}
