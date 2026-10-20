"""Real FastAPI + workers against a disposable local schema. Never public data.

Only invoked by Playwright with EVIDENCEAI_E2E=1. Hard-coded loopback binding,
loopback DB validation, generated schema and temporary storage prevent destructive
tests from targeting the normal API or existing application records.
"""
from contextlib import contextmanager
from pathlib import Path
import os
import hashlib
import json
import shutil
import signal
import sys
import tempfile
from threading import Event, Thread
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'api'))
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'infra/testing'))
from database_guard import activate
activate()  # Never inherit the development DATABASE_URL, including indirect engines.

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema
import httpx
import uvicorn

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services import document_jobs, embedding_jobs
from app.services.document_storage import LocalDocumentStorage, get_document_storage


def no_paid_calls(*args,**kwargs):
    raise RuntimeError('Outbound HTTP disabled in isolated browser tests')


@contextmanager
def environment():
    if os.environ.get('EVIDENCEAI_E2E')!='1':
        raise RuntimeError('Explicit isolated E2E mode required')
    configured=Settings()
    url=make_url(configured.database_url.get_secret_value())
    if url.host not in {'localhost','127.0.0.1'} or configured.app_env not in {'development','test'}:
        raise RuntimeError('E2E requires a loopback development/test database')
    schema='e2e_web_'+uuid.uuid4().hex
    control=create_engine(configured.database_url.get_secret_value(),hide_parameters=True)
    scratch=None
    stop=Event()
    thread=None
    try:
        with control.begin() as connection:connection.execute(CreateSchema(schema))
        scratch=create_engine(configured.database_url.get_secret_value(),hide_parameters=True,
            execution_options={'schema_translate_map':{None:schema}},
            connect_args={'options':f'-c search_path={schema},public -c statement_timeout=15000 -c lock_timeout=5000'})
        Base.metadata.create_all(scratch)
        factory=sessionmaker(scratch,expire_on_commit=False)
        with tempfile.TemporaryDirectory(prefix='evidenceai-e2e-') as temporary:
            settings=Settings(_env_file=None,database_url=configured.database_url,app_env='test',auth_allow_insecure_http=True,
                trusted_frontend_origins=['http://localhost:3100'],auth_rate_limit=10000,
                document_storage_root=Path(temporary).resolve(),embedding_provider='fake',embedding_model='fake-hash-v1',
                embedding_dimensions=128,embedding_hosted_allowed=False,openai_api_key=None,
                llm_provider='mock',llm_model='mock-extractive-v1',llm_hosted_allowed=False,rag_min_similarity=0.0)
            mail=Path(os.environ['EVIDENCEAI_E2E_MAIL_DIR'])
            if mail.parent.resolve()!=Path('/tmp').resolve() or not mail.name.startswith('evidenceai-e2e-mail-'):
                raise RuntimeError('Owned temporary mail fixture required')
            from app.services import registration_service
            def fixture_deliver(settings,email,token):
                target=mail/(hashlib.sha256(email.encode()).hexdigest()+'.json')
                target.write_text(json.dumps({'token':token})); target.chmod(0o600)
                return True
            registration_service.deliver=fixture_deliver
            storage=LocalDocumentStorage(Path(temporary).resolve())
            def isolated_db():
                with factory() as db:
                    try:yield db
                    except BaseException:
                        db.rollback();raise
            import app.core.browser_security as browser
            browser.get_settings=lambda:settings
            app.dependency_overrides[get_db]=isolated_db
            app.dependency_overrides[get_settings]=lambda:settings
            app.dependency_overrides[get_document_storage]=lambda:storage
            app.middleware_stack=None
            httpx.HTTPTransport.handle_request=no_paid_calls
            httpx.AsyncHTTPTransport.handle_async_request=no_paid_calls
            def worker():
                while not stop.is_set():
                    with factory() as db:
                        document_jobs.run_once(db,settings,storage)
                        embedding_jobs.run_once(db,settings)
                    stop.wait(0.25)
            thread=Thread(target=worker,daemon=True);thread.start()
            # Readiness is the existing health endpoint, served only by this process.
            try:
                yield
            finally:
                stop.set()
                if thread:thread.join(timeout=10)
    finally:
        stop.set()
        if thread:thread.join(timeout=10)
        if "mail" in locals(): shutil.rmtree(mail)
        app.dependency_overrides.clear()
        if scratch:scratch.dispose()
        assert schema.startswith('e2e_web_') and len(schema)==40
        with control.begin() as connection:connection.execute(DropSchema(schema,cascade=True))
        control.dispose()


if __name__=='__main__':
    # Uvicorn re-raises its captured signal after shutdown. Convert SIGTERM into
    # normal Python unwinding so the outer schema/storage context always closes.
    def terminate(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, terminate)
    with environment():
        uvicorn.run(app,host='127.0.0.1',port=18000,proxy_headers=False,access_log=False)
