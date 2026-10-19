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

    health = get('/api/health', False)
    assert health['database'] == 'ok'
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
    plugins = {plugin['id']: plugin for plugin in get('/api/plugins')}
    expected = {'elasticsearch', 'grafana-postgresql-datasource',
                'grafana-pyroscope-datasource', 'influxdb', 'jaeger', 'loki',
                'mssql', 'mysql', 'opentsdb', 'prometheus', 'stackdriver', 'tempo', 'zipkin'}
    assert expected <= plugins.keys(), 'An expected bundled datasource is missing'
    # 12.4 includes native core datasources. Grafana marks these trusted
    # built-ins "internal", rather than externally signed "valid". Confirm
    # native identity through the server's core-only API, not an unsigned waiver.
    # External unsigned plugins remain forbidden; the 13.x profile is unchanged.
    native_ids = ({plugin['id'] for plugin in get('/api/plugins?core=1')}
                  if health.get('version') == '12.4.13' else set())
    assert all(plugins[name].get('signature') == 'valid' or
               (name in native_ids and plugins[name].get('signature') == 'internal')
               for name in expected), 'Plugin signature invalid: ' + repr({
                   name: {'signature': plugins[name].get('signature'),
                          'core': plugins[name].get('core'),
                          'baseUrl': plugins[name].get('baseUrl')}
                   for name in sorted(expected)})
    print(json.dumps({'health': 'PASS', 'anonymous_denied': 'PASS',
                      'admin_authentication': 'PASS', 'signup_disabled': 'PASS',
                      'dashboard_provisioning': 'PASS', 'datasource_health': 'PASS',
                      'prometheus_query_targets_up': len(targets),
                      'grafana_version': health.get('version'), 'grafana_commit': health.get('commit'),
                      'bundled_plugin_signatures': 'PASS',
                      'native_internal_plugins': sorted(name for name in expected if plugins[name].get('signature') == 'internal'),
                      'bundled_plugin_versions': {name: plugins[name]['info'].get('version') for name in sorted(expected)}}))


if __name__ == '__main__':
    verify(sys.stdin.read().strip())
