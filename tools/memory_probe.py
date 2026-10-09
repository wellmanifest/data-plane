#!/usr/bin/env python3
"""Linux process PSS/RSS and optional cgroup v2 snapshot; no sampling daemon."""
import argparse,json,os
from datetime import datetime,timezone
from pathlib import Path

def probe(pid,cgroup=None):
    report={'pid':pid,'at':datetime.now(timezone.utc).isoformat(),'scope':'one-process-plus-optional-explicit-cgroup','process':{},'cgroup':{},'warnings':[]}
    try:
        for line in (Path('/proc')/str(pid)/'smaps_rollup').read_text().splitlines():
            if ':' not in line:continue
            name,value=line.split(':',1)
            if name in ['Rss','Pss','Private_Clean','Private_Dirty','Shared_Clean','Shared_Dirty','Swap']:
                report['process'][name+'Bytes']=int(value.split()[0])*1024
    except (OSError,ValueError):report['warnings'].append('Process smaps_rollup unavailable')
    if cgroup:
        base=Path(cgroup)
        for name in ['memory.current','memory.peak','memory.max']:
            try:
                raw=(base/name).read_text().strip();report['cgroup'][name]=int(raw) if raw!='max' else 'max'
            except (OSError,ValueError):report['warnings'].append(name+' unavailable')
        for name in ['memory.stat','memory.events']:
            try:report['cgroup'][name]={k:int(v) for k,v in (line.split() for line in (base/name).read_text().splitlines())}
            except (OSError,ValueError):report['warnings'].append(name+' unavailable')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pid',type=int,default=os.getpid());p.add_argument('--cgroup');a=p.parse_args()
    print(json.dumps(probe(a.pid,a.cgroup),indent=2))
