#!/usr/bin/env python3
"""Normalize every high/critical image finding; never suppress a gate finding."""
import argparse
import hashlib
import json
from pathlib import Path


def inventory(directory,names=('api','web','backup','proxy')):
    rows=[];images={}
    for name in names:
        path=directory/(name+'.json')
        data=json.loads(path.read_text())
        images[name]={'scan_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                      'artifact':data.get('ArtifactName'),'artifact_id':data.get('ArtifactID'),
                      'created_at':data.get('CreatedAt'),'os':data.get('Metadata',{}).get('OS')}
        for result in data.get('Results',[]):
            for finding in result.get('Vulnerabilities',[]):
                if finding['Severity'] not in {'HIGH','CRITICAL'}: continue
                rows.append({'image':name,'target':result['Target'],'class':result.get('Class'),
                    'id':finding['VulnerabilityID'],'package':finding['PkgName'],
                    'installed':finding['InstalledVersion'],'fixed':finding.get('FixedVersion') or None,
                    'severity':finding['Severity'],'status':finding.get('Status'),
                    'url':finding.get('PrimaryURL'),
                    'remediation':'Upgrade to listed fixed version' if finding.get('FixedVersion') else 'Vendor fix absent in this distribution; evaluate supported newer base',
                    'reachability':'Present in runtime image; reachability requires individual review, no exception granted'})
    return {'images':images,'finding_occurrences':len(rows),'distinct_advisories':len({r['id'] for r in rows}),'findings':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--images',nargs='+',default=['api','web','backup','proxy'])
    args=parser.parse_args();args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(inventory(args.directory,args.images),indent=2)+'\n')
