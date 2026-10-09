#!/usr/bin/env python3
"""Synthetic SQLite conformance RAM probe; excludes PG, Redis, gateway and LLM."""
import argparse,json,os,resource,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from conformance.event_store import Store,relay
from memory_probe import probe

def run(count):
    if not 1<=count<=100000:raise ValueError('Count must be 1..100000')
    tenant='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';stream='urn:uuid:11111111-1111-4111-8111-111111111111'
    samples=[]
    def sample(phase):
        reading=probe(os.getpid())
        samples.append({'phase':phase,'memory':reading['process'],'warnings':reading['warnings']})
    sample('python-start');start=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='data-plane-memory-') as temp:
        s=Store(Path(temp)/'source.sqlite');t=Store(Path(temp)/'target.sqlite',authority='authority:replica')
        try:
            sample('two-stores-open')
            for i in range(count):
                s.append(tenant,stream,1,i,str(i))
                if (i+1)%1000==0:sample('append-'+str(i+1))
            appended=time.monotonic()
            delivered=0
            while True:
                n=relay(s,t);delivered+=n
                if not n:break
            sample('relay-complete');relayed=time.monotonic()
            t.rebuild();sample('replay-complete');finished=time.monotonic()
            assert s.value(tenant,stream)==t.value(tenant,stream)==count
            disk=sum(p.stat().st_size for p in Path(temp).glob('*') if p.is_file())
        finally:s.close();t.close()
    return {'scope':'synthetic-python-sqlite-conformance-only','events':count,'delivered':delivered,'eventType':'counter.changed','sourceAndTargetFiles':2,
            'sampledMemory':samples,'peakRssBytesLinux':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            'diskBytesBeforeCloseIncludingWal':disk,'seconds':{'append':appended-start,'relay':relayed-appended,'replay':finished-relayed},
            'notMeasured':['postgresql','redis','production-gateway','LLM','noVNC','large-payload-domain'],'constantMemoryProven':False}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--events',type=int,default=10000);a=p.parse_args()
    print(json.dumps(run(a.events),indent=2))
