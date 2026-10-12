import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from check_docs import check

REVISION='ab'*20
# Minimal stand-in for the pinned checker: rejects missing/divergent adoption and a missing index.
STRICT_CHECKER='''import argparse,hashlib,json,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root');p.add_argument('--standard-revision');p.add_argument('--base');a=p.parse_args()
root=Path(a.root);findings=[]
policy=hashlib.sha256((Path(__file__).parent/'policy.json').read_bytes()).hexdigest()
try:
    adoption=json.loads((root/'.governance/docs.json').read_text())
    if adoption['source_revision']!=a.standard_revision or adoption['policy_sha256']!=policy:raise ValueError
except (OSError,ValueError,KeyError):findings.append({'code':'DOCS_ADOPTION'})
if not (root/'docs/README.md').exists():findings.append({'code':'DOCS_INDEX'})
print(json.dumps({'ok':not findings,'findings':findings}));sys.exit(1 if findings else 0)
'''
PERMISSIVE_CHECKER='import json;print(json.dumps({"ok":True,"findings":[]}))\n'

def git(*args,cwd):
    subprocess.run(['git',*args],cwd=cwd,check=True,capture_output=True)

def fixture(temp,checker_source,policy_digest=None):
    standard=Path(temp)/'standard/docs/standard';standard.mkdir(parents=True)
    (standard/'policy.json').write_text('{"schema":"wellmanifest.docs/policy/v1"}\n')
    (standard/'check.py').write_text(checker_source)
    digest=policy_digest or hashlib.sha256((standard/'policy.json').read_bytes()).hexdigest()
    repo=Path(temp)/'repo';(repo/'.governance').mkdir(parents=True);(repo/'docs').mkdir()
    (repo/'.governance/docs.json').write_text(json.dumps({'schema':'wellmanifest.docs/adoption/v1','repository':'example/repo',
        'standard':'wellmanifest/docs','source_revision':REVISION,'policy_sha256':digest},indent=2)+'\n')
    (repo/'docs/README.md').write_text('# Docs\n')
    git('init','-q',cwd=repo);git('add','-A','-f',cwd=repo)
    git('-c','user.name=t','-c','user.email=t@invalid','commit','-q','-m','fixture',cwd=repo)
    return repo,Path(temp)/'standard'

@unittest.skipUnless(shutil.which('git'),'git is required; the slim Docker image runs these as skipped')
class DocsGate(unittest.TestCase):
    def test_gate_passes_and_every_canary_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo,standard=fixture(temp,STRICT_CHECKER)
            result=check(root=repo,checkout=standard,revision=REVISION,base='')
            self.assertEqual(result['status'],'passed')
            self.assertFalse(result['baseApplied'])
            self.assertFalse(result['protectedEnforcementProven'])
            self.assertEqual([c['canary'] for c in result['canaries']],
                ['missing-adoption','divergent-policy-digest','missing-index','wrong-standard-revision'])
            self.assertEqual(subprocess.run(['git','status','--porcelain'],cwd=repo,capture_output=True,text=True).stdout,'')

    def test_permissive_checker_fails_the_canaries(self):
        with tempfile.TemporaryDirectory() as temp:
            repo,standard=fixture(temp,PERMISSIVE_CHECKER)
            with self.assertRaisesRegex(RuntimeError,'Canary missing-adoption was not rejected'):
                check(root=repo,checkout=standard,revision=REVISION,base='')

    def test_failed_gate_is_not_reported_as_passed(self):
        with tempfile.TemporaryDirectory() as temp:
            repo,standard=fixture(temp,STRICT_CHECKER)
            (repo/'docs/README.md').unlink()
            with self.assertRaisesRegex(RuntimeError,'Docs gate failed'):
                check(root=repo,checkout=standard,revision=REVISION,base='')

    def test_policy_digest_mismatch_stops_before_checker(self):
        with tempfile.TemporaryDirectory() as temp:
            repo,standard=fixture(temp,STRICT_CHECKER,policy_digest='0'*64)
            with self.assertRaisesRegex(RuntimeError,'policy digest differs'):
                check(root=repo,checkout=standard,revision=REVISION,base='')

    def test_untrusted_revision_and_base_shapes_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            repo,standard=fixture(temp,STRICT_CHECKER)
            with self.assertRaisesRegex(RuntimeError,'full trusted commit'):
                check(root=repo,checkout=standard,revision='main',base='')
            with self.assertRaisesRegex(RuntimeError,'full commit SHA'):
                check(root=repo,checkout=standard,revision=REVISION,base='HEAD~1')

if __name__=='__main__':
    unittest.main()
