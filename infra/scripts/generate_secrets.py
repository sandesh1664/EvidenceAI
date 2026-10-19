#!/usr/bin/env python3
"""Generate new deployment secrets without printing values or overwriting existing files."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess


def create(path,value,mode):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
    os.fchmod(descriptor,mode)
    with os.fdopen(descriptor,'w') as stream: stream.write(value+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--identity-output',type=Path,required=True,help='Private offline recovery identity; preserve separately from the host')
    parser.add_argument('--backup-image',default='evidenceai-backup:m11')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    if any(path.resolve()==root or root in path.resolve().parents for path in (args.directory,args.identity_output)):
        raise SystemExit('Keep secrets and recovery identities outside the source checkout')
    directory=args.directory
    if not directory.is_absolute() or directory.exists(): raise SystemExit('Choose a new absolute private secrets directory')
    identity=args.identity_output
    if not identity.is_absolute() or identity.exists() or not identity.parent.is_dir(): raise SystemExit('Choose a new identity file in an existing private directory')
    if identity.parent.stat().st_mode & 0o077: raise SystemExit('Identity parent must have mode 0700')
    result=subprocess.run(['docker','run','--rm','--network','none','--entrypoint','age-keygen',args.backup_image],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    key=result.stdout.decode();recipient=next(line.split(': ',1)[1] for line in key.splitlines() if line.startswith('# public key:'))
    create(identity,key.strip(),0o600)
    directory.mkdir(mode=0o700)
    # Files are readable by their explicitly authorized non-root containers. The host
    # parent directory protects them; file-backed Compose secret uid/gid remapping is not assumed.
    for name in ('db_password','postgres_password','operations_token','grafana_password'):
        create(directory/name,secrets.token_hex(32),0o444)
    create(directory/'provider_key','',0o444)
    print('Secret files created. Keep the recovery identity offline; only the public recipient is needed for normal backup.')
    print('AGE_RECIPIENT='+recipient)


if __name__=='__main__': main()
