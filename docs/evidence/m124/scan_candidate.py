"""Scan one explicitly selected experiment, never replace production references."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'infra/scripts'))
from scan_images import SCANNER

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--name',required=True)
parser.add_argument('--reference',required=True)
args=parser.parse_args()
if not re.fullmatch('[a-z0-9-]+',args.name):parser.error('Simple experiment name required')
if not (re.fullmatch(r'grafana/grafana@sha256:[a-f0-9]{64}',args.reference) or args.reference in {
        'evidenceai-grafana:experimental-m124', 'evidenceai-grafana:kin-m124',
        'evidenceai-grafana:combined-m124'}):
    parser.error('Pinned official digest or the explicit isolated local experiment required')
directory=ROOT/'infra/runtime/m124'/args.name
directory.mkdir(parents=True,exist_ok=True)
archives=directory/'archives';archives.mkdir(exist_ok=True)
cache=ROOT/'infra/runtime/m124/support/trivy-cache'
commands=[]
def run(cmd,log):
    start=time.monotonic();result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
    commands.append({'command':cmd,'exit_code':result.returncode,'seconds':round(time.monotonic()-start,3)})
    (directory/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    result.check_returncode()
with (directory/'scan.log').open('w') as log:
    if args.reference.startswith('grafana/'):
        run(['docker','pull',args.reference],log)
    run(['docker','save',args.reference,'-o',str(archives/'grafana.tar')],log)
    run(['docker','run','--rm','-v',str(archives)+':/scan:ro','-v',str(directory)+':/reports',
         '-v',str(cache)+':/root/.cache',SCANNER,'image','--input','/scan/grafana.tar',
         '--scanners','vuln,secret','--format','json','--output','/reports/grafana.json'],log)
    # Same unsuppressed policy as the release scanner, evaluated from full JSON.
    check=subprocess.run(['python3',str(ROOT/'docs/evidence/m122/check_scan_policy.py'),str(directory/'grafana.json')],capture_output=True,text=True)
    policy=json.loads(check.stdout)
    result={'reference':args.reference,'name':args.name,'policy':policy,'policy_exit_code':check.returncode,'commands':commands}
    (directory/'gate.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
raise SystemExit(check.returncode)
