"""Verify historical normalization disclosure without changing any old evidence."""
import hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[3];manifest=root/'docs/evidence/m124/evidence-sha256.json';audit=json.loads((manifest.parent/'normalization-audit.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
original=json.loads(manifest.read_text());differences={p for p,h in original.items() if sha(root/p)!=h}
normalized={r['file'] for r in audit['files']}
updated_docs={'docs/release-acceptance.md','docs/release-checklist.md','infra/monitoring/grafana-rebuild/README.md'}
assert differences == normalized | updated_docs
for path in updated_docs:
 assert hashlib.sha256(subprocess.check_output(['git','show','932f75f:'+path])).hexdigest()==original[path]
for row in audit['files']:
 assert original[row['file']]==row['original_sha256']
 assert sha(root/row['file'])==row['normalized_sha256']
assert subprocess.check_output(['git','show','932f75f:docs/evidence/m124/evidence-sha256.json'])==manifest.read_bytes()
recovery=json.loads((root/'docs/evidence/m125/historical-recovery.json').read_text())
import gzip
for row in recovery['files']:
 assert hashlib.sha256(gzip.decompress((root/row['recovered_archive']).read_bytes())).hexdigest()==row['original_manifest_sha256']
report={'review':'PASS','original_byte_integrity':'PASS for all four append-only recovered byte streams; current historical normalized paths still differ', 'recovery_evidence':'docs/evidence/m125/historical-recovery.json','historical_manifest_preserved':True,'manifest_sha256':sha(manifest),'files_checked':len(original),'mismatches':sorted(differences), 'normalized_historical_file_mismatches':sorted(normalized), 'intentional_current_documentation_updates':sorted(updated_docs),'all_four_match_disclosed_normalized_hashes':True,'historical_directory_unchanged_since_baseline':subprocess.run(['git','diff','--exit-code','932f75f','--','docs/evidence/m124'],stdout=subprocess.DEVNULL).returncode==0}
(root/'docs/evidence/m125/historical-review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
