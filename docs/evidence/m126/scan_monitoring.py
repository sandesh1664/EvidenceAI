"""Fresh unsuppressed full-image scans of existing immutable monitoring artifacts."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'infra/scripts'))
from scan_images import SCANNER
OTHER = '--other-runtime' in sys.argv
OUT=ROOT/('infra/runtime/m126/runtime-scans' if OTHER else 'infra/runtime/m126/scans')
EVIDENCE=ROOT/'docs/evidence/m126'
OUT.mkdir(parents=True,exist_ok=True)
CACHE=ROOT/'infra/runtime/m126/scans/cache';CACHE.mkdir(parents=True,exist_ok=True)
images={
 'selected':'grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f',
 'upstream-124':'grafana/grafana@sha256:41bbc1b5e04416f81891806076db2a2ff60a5d4da5f78d36a88b033a8c199185',
 'custom-125':'evidenceai-grafana:kin-m125',
}
if OTHER:
 images={name:'evidenceai-'+name+':m121' for name in ('api','web','backup','proxy','database','prometheus','exporter')}
PREFIX='runtime-' if OTHER else ''
rows={};commands=[]
def run(cmd,log):
 r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
 commands.append({'command':cmd,'exit_code':r.returncode,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 (EVIDENCE/(PREFIX+'scan-commands.json')).write_text(json.dumps(commands,indent=2)+'\n')
 r.check_returncode()
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
with (OUT/'scanner.log').open('x') as log:
 run(['docker','run','--rm',SCANNER,'--version'],log)
 # Explicit download in a new cache; no --skip-db-update, ignore files or VEX.
 run(['docker','run','--rm','-v',str(CACHE)+':/root/.cache',SCANNER,'image','--download-db-only'],log)
 for name,reference in images.items():
  directory=OUT/name;directory.mkdir()
  archive=directory/'image.tar'
  inspect=json.loads(subprocess.check_output(['docker','image','inspect',reference]))[0]
  run(['docker','save',reference,'-o',str(archive)],log)
  run(['docker','run','--rm','-v',str(directory)+':/scan','-v',str(CACHE)+':/root/.cache',SCANNER,'image','--input','/scan/image.tar','--scanners','vuln,secret','--format','json','--output','/scan/report.json'],log)
  report=directory/'report.json';d=json.loads(report.read_text())
  findings=[{'target':r['Target'],**{k:v.get(k) for k in ('VulnerabilityID','PkgName','InstalledVersion','FixedVersion','Severity','PrimaryURL')}} for r in d.get('Results',[]) for v in r.get('Vulnerabilities',[])]
  secrets=sum(len(r.get('Secrets',[])) for r in d.get('Results',[]))
  counts={s:sum(v['Severity']==s for v in findings) for s in ('HIGH','CRITICAL','MEDIUM','LOW','UNKNOWN')}
  rows[name]={'reference':reference,'docker_id':inspect['Id'],'repo_digests':inspect.get('RepoDigests'),'architecture':inspect['Architecture'],'rootfs_diff_ids':inspect['RootFS']['Layers'],'archive_sha256':sha(archive),'report_sha256':sha(report),'scan_created_at':d.get('CreatedAt'),'counts':counts,'secrets':secrets,'policy':'FAIL' if counts['HIGH'] or counts['CRITICAL'] or secrets else 'PASS','findings':findings}
  print(name,counts,'secrets',secrets,flush=True)
  (EVIDENCE/('runtime-inventory.json' if OTHER else 'monitoring-inventory.json')).write_text(json.dumps({'scanner':SCANNER,'database':json.loads((CACHE/'trivy/db/metadata.json').read_text()),'images':rows,'candidate_promoted':False},indent=2)+'\n')
raise SystemExit(1 if any(r['policy']=='FAIL' for r in rows.values()) else 0)
