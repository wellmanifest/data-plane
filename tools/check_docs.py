#!/usr/bin/env python3
"""Run the pinned wellmanifest/docs gate and its negative canaries; never modify an existing checkout."""
import hashlib,json,os,re,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADOPTION='.governance/docs.json'
SHA=re.compile(r'[0-9a-f]{40}')
# Each canary mutates a copy of the tracked tree; the pinned checker must reject it with the named code.
CANARIES=[
    ('missing-adoption','DOCS_ADOPTION',lambda tree:(tree/ADOPTION).unlink()),
    ('divergent-policy-digest','DOCS_ADOPTION',lambda tree:_set_adoption(tree,policy_sha256='0'*64)),
    ('missing-index','DOCS_INDEX',lambda tree:(tree/'docs/README.md').unlink()),
]

def _set_adoption(tree,**fields):
    path=tree/ADOPTION;data=json.loads(path.read_text());data.update(fields)
    path.write_text(json.dumps(data,indent=2)+'\n')

def git(*args,cwd):
    return subprocess.run(['git',*args],cwd=cwd,check=True,capture_output=True,text=True).stdout.strip()

def standard_checkout(revision):
    configured=os.environ.get('DOCS_STANDARD_ROOT')
    checkout=Path(configured).resolve() if configured else ROOT/'build/upstream-docs'
    if not checkout.exists():
        if configured:raise RuntimeError('DOCS_STANDARD_ROOT does not exist')
        checkout.mkdir(parents=True)
        git('init','-q',str(checkout),cwd=ROOT)
        git('fetch','--quiet','--depth','1','https://github.com/wellmanifest/docs.git',revision,cwd=checkout)
        git('checkout','--quiet','--detach','FETCH_HEAD',cwd=checkout)
    if git('rev-parse','HEAD',cwd=checkout)!=revision:raise RuntimeError('Docs standard commit mismatch; existing checkout left unchanged')
    return checkout

def run_checker(checker,root,revision,base=None):
    args=[sys.executable,'-I',str(checker),'--root',str(root),'--standard-revision',revision]
    if base:args+=['--base',base]
    done=subprocess.run(args,capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    try:result=json.loads(done.stdout)
    except ValueError:raise RuntimeError('Docs checker returned no JSON: '+done.stderr[-2000:])
    return done.returncode,result

def tracked_copy(root,target,repository):
    """Copy tracked bytes into a fresh repository so a mutation cannot touch the real checkout."""
    git('init','-q',str(target),cwd=root)
    for name in git('ls-files','-z',cwd=root).split('\0'):
        if not name:continue
        destination=target/name;destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes((root/name).read_bytes())
    git('remote','add','origin',f'https://github.com/{repository}.git',cwd=target)
    git('add','-A','-f',cwd=target)
    git('-c','user.name=docs-canary','-c','user.email=docs-canary@invalid','commit','-q','-m','canary baseline',cwd=target)

def rejected(code,result,expected):
    return code!=0 and result.get('ok') is False and any(f.get('code')==expected for f in result.get('findings',[]))

def check(root=ROOT,checkout=None,revision=None,base=None):
    revision=revision or os.environ.get('DOCS_STANDARD_REVISION','')
    if not SHA.fullmatch(revision):raise RuntimeError('DOCS_STANDARD_REVISION must be the full trusted commit from CI configuration')
    base=base if base is not None else os.environ.get('DOCS_BASE_SHA','')
    if base and not SHA.fullmatch(base):raise RuntimeError('DOCS_BASE_SHA must be a full commit SHA')
    if base=='0'*40:base=''  # new branch push: no trusted base, so the run is an audit, not the full gate
    adoption=json.loads((root/ADOPTION).read_text())
    checkout=checkout or standard_checkout(revision)
    if adoption.get('source_revision')!=revision:raise RuntimeError('Adoption pin differs from the trusted standard revision')
    if hashlib.sha256((checkout/'docs/standard/policy.json').read_bytes()).hexdigest()!=adoption.get('policy_sha256'):
        raise RuntimeError('Adoption policy digest differs from the pinned standard bytes')
    checker=checkout/'docs/standard/check.py'
    code,gate=run_checker(checker,root,revision,base or None)
    if code!=0 or not gate.get('ok'):raise RuntimeError('Docs gate failed: '+json.dumps(gate))
    canaries=[]
    with tempfile.TemporaryDirectory(prefix='docs-canary-') as scratch:
        for name,expected,mutate in [*CANARIES,('wrong-standard-revision','DOCS_ADOPTION',None)]:
            tree=Path(scratch)/name;tracked_copy(root,tree,adoption['repository'])
            if mutate:mutate(tree);code,result=run_checker(checker,tree,revision)
            else:code,result=run_checker(checker,tree,'0'*40)
            if not rejected(code,result,expected):raise RuntimeError(f'Canary {name} was not rejected with {expected}: '+json.dumps(result))
            canaries.append({'canary':name,'rejectedWith':expected})
    return {'status':'passed','standardRevision':revision,'baseApplied':bool(base),'gate':gate,'canaries':canaries,
            'scope':'pinned-docs-gate-and-negative-canaries','protectedEnforcementProven':False}

if __name__=='__main__':print(json.dumps(check(),indent=2))
