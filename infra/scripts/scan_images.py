#!/usr/bin/env python3
"""Export/scan only selected images in a dedicated directory, fail on HIGH/CRITICAL.

No Docker socket or broad host mounts enter the third-party scanner. Full reports
retain lower severity findings too. --tag is only for locally built candidates.
"""
import argparse
import json
from pathlib import Path
import subprocess

SCANNER='aquasec/trivy@sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222'
def supporting_images(tag):
    return {**{name:'evidenceai-'+name+':'+tag for name in ('database','prometheus','exporter')},
        'grafana':'grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f'}



def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--tag',default='m121');parser.add_argument('--support-only',action='store_true')
    args=parser.parse_args();root=args.directory.resolve();root.mkdir(parents=True,exist_ok=True)
    archives=root/'archives';archives.mkdir(exist_ok=True);cache=root/'trivy-cache';cache.mkdir(exist_ok=True)
    images=supporting_images(args.tag) if args.support_only else {name:'evidenceai-'+name+':'+args.tag for name in ('api','web','backup','proxy')}
    summary={}
    for name,reference in images.items():
        subprocess.run(['docker','image','inspect',reference],check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['docker','save',reference,'-o',str(archives/(name+'.tar'))],check=True)
        with (root/(name+'-scanner.log')).open('w') as log:
            subprocess.run(['docker','run','--rm','-v',str(archives)+':/scan:ro','-v',str(root)+':/reports',
                '-v',str(cache)+':/root/.cache/',SCANNER,'image','--input','/scan/'+name+'.tar',
                '--scanners','vuln,secret','--format','json','--output','/reports/'+name+'.json'],check=True,stdout=log,stderr=log)
        data=json.loads((root/(name+'.json')).read_text())
        blockers=[v for result in data.get('Results',[]) for v in result.get('Vulnerabilities',[]) if v['Severity'] in {'HIGH','CRITICAL'}]
        secrets=[s for result in data.get('Results',[]) for s in result.get('Secrets',[])]
        summary[name]={'reference':reference,'high':sum(v['Severity']=='HIGH' for v in blockers),
                       'critical':sum(v['Severity']=='CRITICAL' for v in blockers),'secrets':len(secrets)}
    (root/'gate.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    raise SystemExit(1 if any(r['high'] or r['critical'] or r['secrets'] for r in summary.values()) else 0)


if __name__=='__main__':main()
