#!/usr/bin/env python3
"""Public release provenance only: code revision and local image IDs, never secrets."""
import argparse
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import subprocess


def output(command): return subprocess.check_output(command,text=True).strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if output(['git','status','--porcelain','--','.',':(exclude)release/']): raise SystemExit('Release packaging requires a clean committed source tree')
    revision=output(['git','rev-parse','HEAD'])
    images={}
    for name in ('api','web','backup','proxy'):
        ref=f'evidenceai-{name}:sha-{revision}'
        images[name]={'tag':ref,'image_id':output(['docker','image','inspect',ref,'--format','{{.Id}}'])}
    checksums={}
    for path in sorted(args.output.parent.iterdir()):
        if path.suffix in {'.tar','.gz'} and path.is_file():
            with path.open('rb') as stream: checksums[path.name]=hashlib.file_digest(stream,'sha256').hexdigest()
    report={'artifact_sha256':checksums,'version':1,'revision':revision,'created_at':datetime.now(timezone.utc).isoformat(),'images':images,
            'note':'Local image IDs are not registry manifest digests. After operator promotion, record registry @sha256 references in deployment env.'}
    args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
