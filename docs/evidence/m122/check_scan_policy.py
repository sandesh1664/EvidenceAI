"""Evaluate retained full reports using the unchanged HIGH/CRITICAL/secret policy."""
import json
from pathlib import Path
import sys

reports = [json.loads(Path(path).read_text()) for path in sys.argv[1:]]
if not reports:
    raise SystemExit('Reports required')
blockers = []
secrets = []
for report in reports:
    if report.get('SchemaVersion') != 2 or 'Results' not in report:
        raise SystemExit('Incomplete report')
    for result in report['Results']:
        blockers += [v for v in result.get('Vulnerabilities', [])
                     if v['Severity'] in {'HIGH', 'CRITICAL'}]
        secrets += result.get('Secrets', [])
print(json.dumps({'high_critical_occurrences': len(blockers), 'secrets': len(secrets),
                  'status': 'FAIL' if blockers or secrets else 'PASS'}))
raise SystemExit(1 if blockers or secrets else 0)
