"""Capture public vendor metadata without changing or building application artifacts."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'docs/evidence/m126';RAW=ROOT/'infra/runtime/m126/vendor';RAW.mkdir(parents=True,exist_ok=True)
if (OUT/'vendor-review.json').exists(): raise SystemExit('Refusing to overwrite vendor evidence')
urls={
 'grafana-releases':'https://api.github.com/repos/grafana/grafana/releases?per_page=100',
 'grafana-133':'https://api.github.com/repos/grafana/grafana/releases/tags/v13.3.0',
 'tempo-policy':'https://grafana.com/docs/tempo/latest/set-up-for-tracing/setup-tempo/recommended-versions/',
 'cloud-migration':'https://grafana.com/docs/grafana/latest/administration/migration-guide/manually-migrate-to-grafana-cloud/',
 'cloud-private':'https://grafana.com/docs/grafana-cloud/observe-and-act/connect-externally-hosted/private-data-source-connect/',
 'registry-selected':'https://hub.docker.com/v2/repositories/grafana/grafana/tags/13.2.4',
 'registry-124':'https://hub.docker.com/v2/repositories/grafana/grafana/tags/12.4.13',
 'query-fix':'https://api.github.com/repos/grafana/tempo/commits/650eb1985a0776789c8564122990f588a742356f',
 's3-fix':'https://api.github.com/repos/grafana/tempo/commits/bb8ca663db34a0980c9758b40d918fda3b4dbec3',
 'query-ancestry':'https://api.github.com/repos/grafana/tempo/compare/650eb1985a0776789c8564122990f588a742356f...525d1bab07e0',
 's3-ancestry':'https://api.github.com/repos/grafana/tempo/compare/bb8ca663db34a0980c9758b40d918fda3b4dbec3...525d1bab07e0',
}
rows=[]
for name,url in urls.items():
 target=RAW/(name+'.raw')
 cmd=['curl','--silent','--show-error','--location','--output',str(target),'--write-out','%{http_code}',url]
 result=subprocess.run(cmd,capture_output=True,text=True);row={'name':name,'url':url,'command':cmd,'exit_code':result.returncode,'http_status':result.stdout,'raw_path':str(target.relative_to(ROOT))}
 if target.exists():
  row['sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
  try:
   data=json.loads(target.read_text())
   if name=='grafana-releases':row['stable_releases']=[{'tag':r['tag_name'],'published_at':r['published_at']} for r in data if not r.get('prerelease') and not r.get('draft')]
   elif name.startswith('registry'):row['digest']=data.get('digest')
   elif name.endswith('ancestry'):row.update({k:data.get(k) for k in ('status','ahead_by','behind_by','total_commits')})
   elif name.endswith('fix'):row['changed_files']=[{'filename':f['filename'],'patch':f.get('patch')} for f in data.get('files',[])]
  except (ValueError,TypeError):pass
 rows.append(row);print(name,result.returncode,result.stdout,flush=True)
(OUT/'vendor-review.json').write_text(json.dumps(rows,indent=2)+'\n')
# Keep large raw captures outside Git; preserve their original content hashes.
raw_index=[]
for path in OUT.iterdir():
 if path.name in {'support.html','grafana-latest.json','tempo-latest.json','grafana-124.json'}:
  target=RAW/path.name;content=path.read_bytes();target.write_bytes(content)
  raw_index.append({'original_capture':str(path.relative_to(ROOT)),'retained_path':str(target.relative_to(ROOT)),'sha256':hashlib.sha256(content).hexdigest()})
  path.unlink()
(OUT/'vendor-raw-index.json').write_text(json.dumps(raw_index,indent=2)+'\n')
