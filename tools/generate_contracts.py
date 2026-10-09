#!/usr/bin/env python3
"""Generate transport contracts, not an executable gateway. Python stdlib only."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'

def camel(name):
    return ''.join(part[0].upper() + part[1:] for part in re.split(r'[._-]', name))

def generate(catalog):
    operations = catalog['operations']
    error = {'type':'object','additionalProperties':False,'required':['requestId','error'],
             'properties':{'requestId':{'type':'string','format':'uuid'},'error':{
                 'type':'object','additionalProperties':False,'required':['code','message','retryable'],
                 'properties':{'code':{'type':'string'},'message':{'type':'string'},'retryable':{'type':'boolean'}}}}}
    api = {'openapi':'3.1.0','info':{'title':'Data Plane proposed API','version':catalog['version']},
           'servers':[{'url':'https://gateway.example'}],
           'security':[{'bearerAuth':[]}], 'paths':{},
           'components':{'securitySchemes':{'bearerAuth':{'type':'http','scheme':'bearer'}},'schemas':{'Error':error}}}
    mcp = {'tools':[]}
    definitions = {}
    roots = {'Query':[], 'Mutation':[]}
    def gql_type(schema, name, is_input):
        if 'x-graphql-scalar' in schema:
            return schema['x-graphql-scalar']
        typ = schema.get('type')
        if typ == 'array':
            return '['+gql_type(schema['items'], name+'Item', is_input)+'!]'
        if typ == 'object' and not schema.get('properties'):
            return 'JSON'
        if typ == 'object':
            fields=[]
            required=set(schema.get('required',[]))
            for key, value in schema['properties'].items():
                if not re.fullmatch(r'[_A-Za-z][_0-9A-Za-z]*', key):
                    raise ValueError('JSON key cannot be represented directly in GraphQL: '+key)
                field_type=gql_type(value, name+camel(key), is_input)
                fields.append(f'  {key}: {field_type}'+('!' if key in required else ''))
            definition=('input' if is_input else 'type')+' '+name+' {\n'+'\n'.join(fields)+'\n}'
            if name in definitions and definitions[name] != definition:
                raise ValueError('Conflicting GraphQL type: '+name)
            definitions[name]=definition
            return name
        if typ in {'string','integer','number','boolean'}:
            return {'string':'String','integer':'Int','number':'Float','boolean':'Boolean'}[typ]
        raise ValueError('Unsupported JSON schema structure: '+name)
    for op in operations:
        name=op['name']; typename=camel(name)
        input_name=typename+'Input'; output_name=typename+'Output'
        api['components']['schemas'][input_name]=op['inputSchema']
        api['components']['schemas'][output_name]=op['outputSchema']
        success=str(op['transports']['rest']['successStatus'])
        responses={success:{'description':'Accepted' if success=='202' else 'Operation completed',
                      'content':{'application/json':{'schema':{'$ref':f'#/components/schemas/{output_name}'}}}}}
        for status in [400,401,403,404,409,429,500,503]:
            responses[str(status)]={'description':'Domain or transport error','content':{'application/json':{'schema':{'$ref':'#/components/schemas/Error'}}}}
        api['paths'][op['transports']['rest']['path']]={'post':{
            'operationId':name.replace('.','_'),'summary':op['description'],'x-operation-uri':op['uri'],
            'requestBody':{'required':True,'content':{'application/json':{'schema':{'$ref':f'#/components/schemas/{input_name}'}}}},
            'responses':responses}}
        readonly=op['effects']==['read']
        mcp['tools'].append({'name':op['transports']['mcp'],'description':op['description'],
            'inputSchema':op['inputSchema'],'outputSchema':op['outputSchema'],
            'annotations':{'readOnlyHint':readonly,'destructiveHint':not readonly,
                           'idempotentHint':True,'openWorldHint':not readonly}})
        it=gql_type(op['inputSchema'],input_name,True)
        ot=gql_type(op['outputSchema'],output_name,False)
        mapping=op['transports']['graphql']
        roots[mapping['root']].append(f'  {mapping["field"]}(input: {it}!): {ot}')
    sdl = '# Generated from operations.json. Runtime MUST also validate JSON Schema constraints.\n'
    sdl += '# Scalar parsers, auth, limits and resolvers are not implemented by this file.\n'
    sdl += '\n'.join('scalar '+s for s in ['JSON','UUID','URN','Revision','Base64'])+'\n\n'
    sdl += '\n\n'.join(definitions.values())+'\n\n'
    sdl += '\n\n'.join('type '+root+' {\n'+'\n'.join(fields)+'\n}' for root,fields in roots.items())+'\n'
    return {'contracts/openapi.json':json_text(api),'contracts/mcp-tools.json':json_text(mcp),'contracts/schema.graphql':sdl}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Report drift without changing files.')
    args=parser.parse_args()
    catalog=json.loads((ROOT/'contracts/operations.json').read_text())
    generated=generate(catalog)
    drift=[]
    for name,content in generated.items():
        dest=ROOT/name
        if args.check:
            if not dest.exists() or dest.read_text()!=content: drift.append(name)
        else:
            dest.write_text(content,encoding='utf-8')
    if drift:
        raise SystemExit('Generated contract drift: '+', '.join(drift))
    print('Contract generation '+('verified' if args.check else 'completed')+f': {len(generated)} files')

if __name__=='__main__':
    main()
