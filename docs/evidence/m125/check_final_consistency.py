"""Cross-check final evidence without modifying application data or historical files."""
from pathlib import Path
import hashlib,json,subprocess,tarfile,xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[3];out=root/'docs/evidence/m125'
read=lambda p:json.loads((root/p).read_text())
inv=read('docs/security-remediation-12-5-inventory.json');release=read('docs/evidence/m125/release-result.json')
assert inv['after']['high']==61 and inv['after']['critical']==0
for name,expected in [('upstream-124',5),('kin',2)]:
 row=inv['experiments'][name];assert row['image']['high']==expected and row['image']['critical']==0 and row['image']['secrets']==0
 assert row['selected_for_production'] is False
assert {r['advisory'] for r in inv['experiments']['kin']['findings']}=={'CVE-2026-21728','CVE-2026-28377'}
assert all(r['image']['high']==r['image']['critical']==r['image']['secrets']==0 for name,r in inv['after']['images'].items() if name!='grafana')
suite=ET.parse(out/'backend.xml').getroot().find('testsuite');assert suite.attrib['tests']=='662' and suite.attrib['failures']==suite.attrib['errors']=='0'
for name in ['backend-verified','browser-final','evaluation-final','isolation-guard-final']:
 r=read('docs/evidence/m125/'+name+'/isolation.json');assert r['exit_code']==0 and r['owned_container_removed'] and r['isolation_clean']
assert read('docs/evidence/m125/browser-final-command.json')['exit_code']==0
assert '18 passed' in (root/'infra/runtime/m125/browser-final.log').read_text()
assert '9 passed' in (out/'isolation-tests-final.log').read_text()
assert read('docs/evidence/m125/evaluation-command.json')['exit_code']==0
assert read('docs/evidence/m125/data-preservation.json')['status']=='PASS'
final=read('docs/evidence/m125/data-preservation-final.json');assert final['status']=='FAIL' and final['table_count_changes']=={'auth_rate_limits':1} and final['private_storage_content_and_metadata_equal']
delta=read('docs/evidence/m125/database-final-delta.json');assert delta['original_limiter_rows_preserved'] and delta['limiter_count_after']==13 and delta['added_record_attribution']=='NOT VERIFIED'
assert release['final_whole_database_equality']=='FAIL' and release['release']=='BLOCKED' and not release['candidate_promoted']
manifest=read('docs/evidence/m125/source-manifest.json')
for name,expected in manifest['source_files'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected,name
for name,row in read('docs/evidence/m125/guard-preservation.json')['preserved'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==row['sha256'],name
assert subprocess.run(['git','diff','--exit-code','932f75f','--','docs/evidence/m124'],stdout=subprocess.DEVNULL).returncode==0
historical=read('docs/evidence/m124/evidence-sha256.json')
with tarfile.open(out/'m124-original-evidence.tar.gz') as tar:
 for name,expected in historical.items():assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==expected,name
assert hashlib.sha256((out.parent/'m124/evidence-sha256.json').read_bytes()).hexdigest()=='27f19c621d4a6e983d42b6aca6b8c41c5786db386f6e17a1d5d8780ba21b4326'
gate=subprocess.run(['python3',str(root/'infra/scripts/verify_release.py'),str(out/'release-result.json')],capture_output=True,text=True);assert gate.returncode==1 and json.loads(gate.stdout)['release']=='BLOCKED'
report={'cross_checks':'PASS','backend':662,'frontend':53,'browsers':18,'isolation_cases':9,'selected_high':61,'candidate_high':2,'original_historical_contents_verified':len(historical),'final_development_equality':'FAIL','original_rows_and_storage':'PASS','writer_attribution':'NOT VERIFIED','production':'BLOCKED','scope':'Consistency of recorded local observations; not a hosted acceptance or missing-writer attribution.'}
(out/'final-consistency.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
