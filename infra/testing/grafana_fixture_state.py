"""Synthetic state probe for smoke.py's owned Grafana only; secret via stdin."""
import base64
import json
import sys
import urllib.request

settings = json.load(sys.stdin)
uid = 'evidenceai-synthetic-upgrade-state'
headers = {'Authorization': 'Basic ' + base64.b64encode(('admin:' + settings['password']).encode()).decode()}
if settings['action'] == 'create':
    headers['Content-Type'] = 'application/json'
    payload = {'dashboard': {'uid': uid, 'title': 'Synthetic upgrade persistence fixture',
                             'schemaVersion': 39, 'version': 0, 'panels': []}, 'overwrite': False}
    request = urllib.request.Request('http://grafana:3000/api/dashboards/db',
                                     headers=headers, data=json.dumps(payload).encode())
    with urllib.request.urlopen(request, timeout=15) as response:
        assert json.load(response)['uid'] == uid
elif settings['action'] != 'verify':
    raise ValueError('Unknown fixture operation')
request = urllib.request.Request('http://grafana:3000/api/dashboards/uid/' + uid, headers=headers)
with urllib.request.urlopen(request, timeout=15) as response:
    result = json.load(response)
    assert result['dashboard']['title'] == 'Synthetic upgrade persistence fixture'
    assert result['dashboard']['version'] == 1
print(json.dumps({'persistent_synthetic_dashboard': 'PASS', 'version': 1}))
