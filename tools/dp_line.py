#!/usr/bin/env python3
"""Shell adapter for data-plane.line/v1. Reads stdin, writes stdout; converts and validates, never executes."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from conformance.line import (LineError,classify,event_to_line,format_line,line_hash,line_to_event,line_to_request,
    line_to_response,load_contracts,parse,request_to_line,response_to_line)

CONTRACT_VIOLATION=2

def validate_request(name,envelope,operations):
    from jsonschema import Draft202012Validator,FormatChecker
    errors=sorted(Draft202012Validator(operations[name]['inputSchema'],format_checker=FormatChecker()).iter_errors(envelope),key=str)
    if errors: raise LineError('Input schema violation at /'+'/'.join(map(str,errors[0].absolute_path)))

def convert(command,item,contracts,name=None):
    if command=='parse':
        kind,target,variables=parse(item)
        return json.dumps({'type':kind,'target':target,'vars':variables,'kind':classify(item,contracts),'sha256':line_hash(item)},ensure_ascii=False,sort_keys=True)
    if command=='canonical':return format_line(*parse(item))
    if command=='check':
        parse(item,strict=True);classify(item,contracts);return None
    if command=='to-request':
        name,envelope=line_to_request(item,contracts);validate_request(name,envelope,contracts[1])
        return json.dumps({'operation':name,'uri':contracts[1][name]['uri'],'input':envelope},ensure_ascii=False,sort_keys=True)
    if command=='from-request':
        envelope=json.loads(item);validate_request(name,envelope,contracts[1]);return request_to_line(name,envelope,contracts)
    if command=='to-response':return json.dumps(line_to_response(item),ensure_ascii=False,sort_keys=True)
    if command=='from-response':return response_to_line(json.loads(item))
    if command=='to-event':return json.dumps(line_to_event(item,contracts),ensure_ascii=False,sort_keys=True,separators=(',',':'))
    if command=='from-event':return event_to_line(json.loads(item),contracts)
    raise LineError('Unknown command')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['parse','canonical','check','to-request','from-request','to-response','from-response','to-event','from-event'])
    p.add_argument('--operation',help='Operation name for from-request')
    p.add_argument('line',nargs='?',help='One line or JSON document; default: every stdin line')
    args=p.parse_args(argv)
    if args.command=='from-request' and not args.operation:p.error('--operation is required for from-request')
    contracts=load_contracts()
    items=[args.line] if args.line is not None else [line for line in sys.stdin.read().splitlines() if line.strip()]
    failed=False
    for number,item in enumerate(items,1):
        try:
            output=convert(args.command,item,contracts,args.operation)
            if output is not None:print(output)
        except (LineError,ValueError,KeyError,TypeError) as error:
            failed=True
            print(json.dumps({'line':number,'error':str(error)}),file=sys.stderr)
    return CONTRACT_VIOLATION if failed else 0

if __name__=='__main__':sys.exit(main())
