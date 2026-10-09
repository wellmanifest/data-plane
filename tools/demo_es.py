#!/usr/bin/env python3
import json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from conformance.event_store import Store,relay
from memory_probe import probe
import os

with tempfile.TemporaryDirectory(prefix='data-plane-demo-') as folder:
    source=Store(Path(folder)/'source.sqlite');target=Store(Path(folder)/'projection.sqlite',authority='authority:replica')
    try:
        tenant='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';stream='urn:uuid:11111111-1111-4111-8111-111111111111'
        for i,delta in enumerate([3,5,-2]):source.append(tenant,stream,delta,i,f'command-{i}')
        transferred=relay(source,target);target.rebuild()
        print(json.dumps({'scope':'synthetic-sqlite-conformance-demo','eventsTransferred':transferred,'sourceValue':source.value(tenant,stream),'projectionValue':target.value(tenant,stream),'memorySnapshot':probe(os.getpid()),'productionRamMeasured':False},indent=2))
    finally:source.close();target.close()
