"""Recreate normalized 12.3 inventory from full local reports and Docker archives."""
from pathlib import Path
import importlib.util
import json
import hashlib
import subprocess

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('m122inventory',ROOT/'docs/evidence/m122/generate_inventory.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
vendors={r['advisory']:r for r in json.loads((ROOT/'docs/evidence/m123/vendor-advisories.json').read_text())}


def normalized(data,name):
    rows=[]
    for result in data.get('Results',[]):
        for v in result.get('Vulnerabilities',[]):
            id=v['VulnerabilityID'];vendor=vendors.get(id,{})
            refs=v.get('References',[])
            url=vendor.get('vendor_url') or next((u for u in refs if '/security/advisories/' in u or '/security-advisories/' in u or 'pkg.go.dev/vuln/' in u),v.get('PrimaryURL'))
            target=result['Target']
            functionality=('Grafana API/server and integrated datasources' if '/bin/grafana' in target else 'Bundled '+target.split('/plugins-bundled/')[-1].split('/')[0]+' datasource' if '/plugins-bundled/' in target else 'Runtime OS/library')
            vendor_severity=vendor.get('vendor_record',{}).get('severity')
            rows.append({'image':name,'advisory':id,'severity':v['Severity'],
                'severity_source':v.get('SeveritySource'),'vendor_severity':vendor_severity,
                'package':v['PkgName'],'installed':v['InstalledVersion'],'fixed':v.get('FixedVersion'),
                'binary_or_target':target,'layer':v.get('Layer'),'dependency_class':result.get('Class'),
                'ecosystem':result.get('Type'),'distribution':data['Metadata'].get('OS'),
                'runtime_functionality':functionality,'title':v.get('Title'),
                'vendor_advisory':url,'scanner_primary_url':v.get('PrimaryURL'),
                'remediation_availability':'Package fixed versions listed; whole-image compatibility/security requires separate acceptance' if v.get('FixedVersion') else 'No fixed version listed by current scanner',
                'verification_status':'Present in freshly scanned runtime. Vendor record retrieved; no exploit reachability exemption or exception approved.' if vendor.get('exit_code')==0 else 'Present in freshly scanned runtime; reference supplied by scanner, not independently retrieved. No exception approved.'})
    return rows


def assessed(directory,name,ref):
    basename='grafana' if name.startswith('upstream') or name in {'grafana','core','plugins','combined'} else name
    metadata,_=previous.image(directory,basename,ref)
    raw=json.loads((directory/(basename+'.json')).read_text())
    all_rows=normalized(raw,name)
    blockers=[r for r in all_rows if r['severity'] in {'HIGH','CRITICAL'}]
    return {'image':metadata,'all_severity_counts':{s:sum(r['severity']==s for r in all_rows) for s in ('CRITICAL','HIGH','MEDIUM','LOW','UNKNOWN')},
        'findings':blockers,'all_findings':all_rows,'unique_blocking_advisories':len({r['advisory'] for r in blockers})}


def main():
    images={};selected_findings=[]
    for group in ('application','support'):
        directory=ROOT/'infra/runtime/m123'/group
        for name,policy in json.loads((directory/'gate.json').read_text()).items():
            item=assessed(directory,name,policy['reference'])
            assert all(item['image'][k]==policy[k] for k in ('high','critical','secrets'))
            images[name]=item;selected_findings+=item['findings']
    experiments={}
    for name in ('core','plugins','combined','upstream-distroless','upstream-131','upstream-124','upstream-130'):
        directory=ROOT/'infra/runtime/m123'/name;policy=json.loads((directory/'gate.json').read_text())
        experiments[name]=assessed(directory,name,policy['reference'])
        experiments[name]['selected_for_production']=False
        assert len(experiments[name]['findings'])==policy['policy']['high_critical_occurrences']
    baseline=json.loads((ROOT/'docs/security-remediation-12-2-inventory.json').read_text())
    before_ids={r['advisory'] for r in images['grafana']['findings']}
    core_ids={r['advisory'] for r in experiments['core']['findings']}
    report={'baseline_git':'5d4571d87b0ab866f0942c4a52bdd0cad89e264c','working_tree_uncommitted':True,
        'scanner_reference':'aquasec/trivy@sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222',
        'vulnerability_database':json.loads((ROOT/'infra/runtime/m123/support/trivy-cache/trivy/db/metadata.json').read_text()),
        'before':{'source':'docs/security-remediation-12-2-inventory.json#/after','high':baseline['after']['high'],'critical':baseline['after']['critical'],'distinct_advisories':baseline['after']['distinct_advisories']},
        'after':{'high':sum(r['image']['high'] for r in images.values()),'critical':sum(r['image']['critical'] for r in images.values()),'distinct_advisories':len({r['advisory'] for r in selected_findings}),'images':images,'findings':selected_findings},
        'experiments':experiments,'core_removed_advisory_ids':sorted(before_ids-core_ids),
        'core_new_blocking_advisory_ids':sorted(core_ids-before_ids),'release':'BLOCKED','approved_exceptions':[]}
    (ROOT/'docs/security-remediation-12-3-inventory.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Verified image archives and live layers. Selected:',report['after']['high'],'high;',report['after']['critical'],'critical')
    for name,row in experiments.items():print(name,row['image']['high'],row['image']['critical'])


if __name__=='__main__':main()
