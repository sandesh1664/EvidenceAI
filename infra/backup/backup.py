"""Quiesced application backup and fail-closed disposable restore verification.

All evidence, filenames and dumps remain inside the encrypted archive or tmpfs.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid

REVISION='91e2b6d8c410'
NAME=re.compile(r'evidenceai-\d{8}T\d{12}Z-[a-f0-9]{32}\.tar\.age')


def run(arguments, **kwargs):
    result=subprocess.run(arguments,stderr=subprocess.DEVNULL,check=False,**kwargs)
    if result.returncode: raise RuntimeError('Backup tool operation failed')
    return result.stdout


def database_env():
    path=os.environ.get('DATABASE_PASSWORD_FILE','/run/secrets/db_password')
    secret=Path(path).read_text().strip()
    if len(secret)<32: raise ValueError('Database secret invalid')
    os.environ['PGPASSWORD']=secret
    os.environ['PGCONNECT_TIMEOUT']='5'


def sql(statement):
    return run(['psql','-X','-A','-t','-v','ON_ERROR_STOP=1','-c',statement],stdout=subprocess.PIPE).decode().strip()


def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def metadata():
    revision=sql('SELECT version_num FROM alembic_version')
    vector=sql("SELECT extversion FROM pg_extension WHERE extname='vector'")
    if revision!=REVISION or not vector: raise ValueError('Schema or pgvector verification failed')
    # Only storage keys/checksums are consumed internally; never output private rows.
    records=json.loads(sql("SELECT coalesce(json_agg(json_build_object('key',storage_key,'sha256',checksum_sha256)), '[]'::json) FROM documents"))
    return revision,vector,records


def backup():
    if os.environ.get('QUIESCED')!='1': raise ValueError('Stop writers through deployment backup command first')
    recipient=os.environ.get('AGE_RECIPIENT','')
    if not re.fullmatch(r'age1[a-z0-9]{58}',recipient): raise ValueError('Age recipient invalid')
    database_env()
    revision,vector,records=metadata()
    started=time.monotonic()
    with tempfile.TemporaryDirectory(dir='/work') as directory:
        root=Path(directory)
        (root/'documents').mkdir(mode=0o700)
        run(['pg_dump','--format=custom','--no-owner','--no-acl','--no-comments','--file',str(root/'database.dump')])
        hashes={}
        for source in Path('/documents').iterdir():
            if not re.fullmatch(r'[a-f0-9]{32}(\.part)?',source.name) or source.is_symlink() or not source.is_file():
                raise ValueError('Unexpected storage object; backup refused')
            target=root/'documents'/source.name
            shutil.copyfile(source,target,follow_symlinks=False)
            target.chmod(0o600)
            hashes['documents/'+source.name]=digest(target)
        for record in records:
            if hashes.get('documents/'+record['key'])!=record['sha256']:
                raise ValueError('Referenced original is unavailable or corrupted')
        hashes['database.dump']=digest(root/'database.dump')
        manifest={'version':1,'schema_revision':revision,'pgvector_version':vector,'document_count':len(records),
                  'file_sha256':hashes,'created_at':datetime.now(timezone.utc).isoformat(),'consistency':'writers stopped'}
        (root/'manifest.json').write_text(json.dumps(manifest))
        archive=root/'bundle.tar'
        with tarfile.open(archive,'w') as tar:
            for item in sorted(root.iterdir()):
                if item!=archive: tar.add(item,arcname=item.name,recursive=True)
        filename='evidenceai-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex+'.tar.age'
        temporary=Path('/backups')/(filename+'.partial')
        try:
            run(['age','--encrypt','--recipient',recipient,'--output',str(temporary),str(archive)])
            os.chmod(temporary,0o600)
            with temporary.open('rb') as stream: os.fsync(stream.fileno())
            temporary.rename(Path('/backups')/filename)
            descriptor=os.open('/backups',os.O_RDONLY|os.O_DIRECTORY)
            try: os.fsync(descriptor)
            finally: os.close(descriptor)
        finally: temporary.unlink(missing_ok=True)
    retention=int(os.environ.get('BACKUP_RETENTION_DAYS','14'))
    if not 1<=retention<=3650: raise ValueError('Retention outside allowed range')
    for item in Path('/backups').iterdir():
        if NAME.fullmatch(item.name) and not item.is_symlink() and time.time()-item.stat().st_mtime>retention*86400:
            item.unlink()
    print(json.dumps({'status':'encrypted_backup_complete','file':filename,'document_count':len(records),
        'storage_file_count':len(hashes)-1,'elapsed_seconds':round(time.monotonic()-started,3)}))


def recovery_directory():
    destination=os.environ.get('RESTORE_DOCUMENTS_TO')
    if not destination: return None
    target=Path(destination)
    if destination!='/restored-documents' or target.is_symlink() or not target.is_dir() or any(target.iterdir()):
        raise ValueError('Recovery documents require an empty isolated mount')
    return target


def restore():
    if os.environ.get('PGHOST')!='restore-db' or os.environ.get('PGDATABASE')!='restorecheck':
        raise ValueError('Restore is restricted to the disposable restore-db/restorecheck target')
    filename=os.environ.get('BACKUP_FILE','')
    if not NAME.fullmatch(filename): raise ValueError('Select an exact encrypted backup filename')
    target=recovery_directory()
    database_env()
    if sql("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")!='0':
        raise ValueError('Restore target must be empty; refusing overwrite')
    started=time.monotonic()
    with tempfile.TemporaryDirectory(dir='/work') as directory:
        root=Path(directory)
        archive=root/'bundle.tar'
        run(['age','--decrypt','--identity','/run/secrets/age_identity','--output',str(archive),'/backups/'+filename])
        with tarfile.open(archive,'r') as tar:
            members=tar.getmembers()
            if sum(member.size for member in members)>2*1024**3: raise ValueError('Restore archive exceeds tmpfs budget')
            for member in members:
                if member.name not in {'manifest.json','database.dump','documents'} and not re.fullmatch(r'documents/[a-f0-9]{32}(\.part)?',member.name):
                    raise ValueError('Unsafe archive entry')
                if not (member.isfile() or member.isdir()): raise ValueError('Archive links are forbidden')
            tar.extractall(root,members=members,filter='data')
        manifest=json.loads((root/'manifest.json').read_text())
        if manifest['version']!=1 or manifest['schema_revision']!=REVISION: raise ValueError('Unsupported backup version')
        for name,checksum in manifest['file_sha256'].items():
            if name!='database.dump' and not re.fullmatch(r'documents/[a-f0-9]{32}(\.part)?',name): raise ValueError('Unsafe manifest path')
            if digest(root/name)!=checksum: raise ValueError('Backup digest mismatch')
        run(['pg_restore','--exit-on-error','--no-owner','--no-acl','--dbname','restorecheck',str(root/'database.dump')])
        revision,vector,records=metadata()
        for record in records:
            key=record['key']
            if not re.fullmatch(r'[a-f0-9]{32}',key) or digest(root/'documents'/key)!=record['sha256']:
                raise ValueError('Restored document verification failed')
        if len(records)!=manifest['document_count']: raise ValueError('Document count mismatch')
        if target is not None:
            # Destination validated before restoring any database objects.
            for source in (root/'documents').iterdir():
                shutil.copyfile(source,target/source.name,follow_symlinks=False)
                (target/source.name).chmod(0o600)
        print(json.dumps({'status':'restore_verified','schema_revision':revision,'pgvector_version':vector,
            'document_count':len(records),'storage_file_count':len(manifest['file_sha256'])-1,
            'elapsed_seconds':round(time.monotonic()-started,3),'scope':'isolated disposable recovery drill'}))


def main():
    try:
        mode=sys.argv[1] if len(sys.argv)>1 else 'backup'
        if mode=='backup': backup()
        elif mode=='restore': restore()
        elif mode=='export':
            filename=os.environ.get('BACKUP_FILE','')
            if not NAME.fullmatch(filename): raise ValueError('Exact backup filename required')
            with (Path('/backups')/filename).open('rb') as source:
                shutil.copyfileobj(source,sys.stdout.buffer)
        elif mode=='list':
            print(json.dumps(sorted(p.name for p in Path('/backups').iterdir() if NAME.fullmatch(p.name))))
        else: raise ValueError('Unknown backup operation')
    except Exception:
        print(json.dumps({'status':'failed','detail':'Backup/recovery failed safely; inspect private configuration and integrity'}),file=sys.stderr)
        raise SystemExit(1) from None


if __name__=='__main__': main()
