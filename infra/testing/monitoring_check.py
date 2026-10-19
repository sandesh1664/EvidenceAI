"""Run inside the isolated smoke API container; password arrives only on stdin.

Checks the actual Grafana API and provisioned datasource, not just process health.
Never print credentials, authorization headers or response bodies on failure.
"""
import base64
import json
import sys
import urllib.error
import urllib.request


def verify(password):
    base = 'http://grafana:3000'
    authorization = 'Basic ' + base64.b64encode(('admin:' + password).encode()).decode()

    def get(path, authenticated=True):
        headers = {'Authorization': authorization} if authenticated else {}
        request = urllib.request.Request(base + path, headers=headers)
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    assert get('/api/health', False)['database'] == 'ok'
    try:
        get('/api/search', False)
    except urllib.error.HTTPError as error:
        assert error.code == 401, 'Anonymous access was not refused with 401'
    else:
        raise AssertionError('Anonymous dashboard access was allowed')
    assert get('/api/user')['isGrafanaAdmin'] is True
    settings = get('/api/admin/settings')
    assert settings['auth.anonymous']['enabled'] == 'false'
    assert settings['users']['allow_sign_up'] == 'false'
    dashboard = get('/api/dashboards/uid/evidenceai-operations')
    assert dashboard['meta']['provisioned'] is True
    assert dashboard['dashboard']['title'] == 'EvidenceAI Operations'
    datasource = get('/api/datasources/uid/evidenceai-prometheus')
    assert datasource['url'] == 'http://prometheus:9090'
    assert datasource['type'] == 'prometheus' and datasource['access'] == 'proxy'
    assert get('/api/datasources/uid/evidenceai-prometheus/health')['status'] == 'OK'
    query = get('/api/datasources/proxy/uid/evidenceai-prometheus/api/v1/query?query=up')
    assert query['status'] == 'success'
    targets = query['data']['result']
    assert len(targets) == 2 and all(row['value'][1] == '1' for row in targets)
    print(json.dumps({'health': 'PASS', 'anonymous_denied': 'PASS',
                      'admin_authentication': 'PASS', 'signup_disabled': 'PASS',
                      'dashboard_provisioning': 'PASS', 'datasource_health': 'PASS',
                      'prometheus_query_targets_up': len(targets)}))


if __name__ == '__main__':
    verify(sys.stdin.read().strip())
