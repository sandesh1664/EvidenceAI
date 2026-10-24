"""Explicit synthetic-only live probe, exclusively inside run_isolated.py resources."""
import argparse
import hashlib
import tempfile
from pathlib import Path
from io import BytesIO
from types import SimpleNamespace
import json
import uuid

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import Settings
from app.db.base import Base
from app.db.disposable_database import activate
from app.models import User, Workspace, WorkspaceMember, Document, DocumentChunk
from app.schemas.ask import AskRequest
from app.services import embedding_jobs, rag_service, search_service
from app.services.embedding_providers import EmbeddingEngine
from app.services.gemini_providers import GeminiEmbeddingProvider, GeminiLLMProvider
from app.services.llm_providers import LLMEngine

TEXT = 'Solar panels convert sunlight into renewable electricity.'
QUESTION = 'What do solar panels convert?'


class ProbeTransport(httpx.AsyncHTTPTransport):
    def __init__(self):
        super().__init__(retries=0)
        self.counts = {'embedding': 0, 'generation': 0}

    async def handle_async_request(self, request):
        kind = 'embedding' if request.url.path.endswith(':batchEmbedContents') else 'generation'
        self.counts[kind] += 1
        if self.counts[kind] > (3 if kind == 'embedding' else 2):
            raise RuntimeError('Synthetic probe request limit reached')
        return await super().handle_async_request(request)


def exercise(db, settings, embedding, generation):
    """Synthetic upload, real extraction, authorized index and grounded research."""
    from app.services.document_storage import LocalDocumentStorage
    from app.services import document_service, document_jobs
    embedding.embed(['Synthetic probe sentence about solar panels.'])
    owner = User(email=uuid.uuid4().hex+'@example.invalid', display_name='Synthetic Gemini probe')
    db.add(owner); db.flush()
    workspace = Workspace(name='Synthetic Gemini probe', owner_id=owner.id)
    db.add(workspace); db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role='owner'))
    db.commit()
    with tempfile.TemporaryDirectory(prefix='evidenceai-synthetic-upload-') as temporary:
        local = settings.model_copy(update={'document_storage_root':Path(temporary).resolve()})
        storage = LocalDocumentStorage(local.document_storage_root)
        file = SimpleNamespace(filename='synthetic-solar.txt', content_type='text/plain', file=BytesIO(TEXT.encode()))
        document = document_service.upload_document(db, workspace.id, owner.id, file, local, storage)
        claim = document_jobs.claim_job(db, local)
        if not claim or not document_jobs.process_claim(db, claim, local, storage):
            raise RuntimeError('Synthetic extraction failed')
        embedding_jobs.request_index(db, workspace.id, document.id, owner.id, local)
        claim = embedding_jobs.claim_job(db, local)
        if not claim or not embedding_jobs.process_claim(db, claim, local, embedding):
            raise RuntimeError('Synthetic indexing failed')
        if embedding_jobs.status_for(db, document.id, local)['state'] != 'done':
            raise RuntimeError('Synthetic indexing failed')
        original = search_service.EmbeddingEngine
        search_service.EmbeddingEngine = lambda _: embedding
        try:
            result = rag_service.ask(db, workspace.id, owner.id, AskRequest(question=QUESTION),
                                     local, engine=generation)
        finally:
            search_service.EmbeddingEngine = original
        if result.body.status != 'answered' or not result.body.citations:
            raise RuntimeError('Synthetic grounded answer failed')
    return {'upload_and_extraction':'PASS', 'indexing':'PASS', 'retrieval_and_citations':'PASS',
            'embedding_identity':embedding.profile.identifier,
            'generation_identity':result.body.model_identifier,
            'usage':result.body.usage.model_dump() if result.body.usage else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorize-synthetic-transfer', action='store_true')
    args = parser.parse_args()
    if not args.authorize_synthetic_transfer:
        parser.error('Explicit synthetic-transfer authorization required')
    summary = {'result': 'BLOCKED', 'development_database_accessed': False,
               'requests': {'embedding': 0, 'generation': 0}}
    control = scratch = transport = None
    created = False
    schema = 'eval_rag_'+uuid.uuid4().hex
    try:
        url = activate()  # Reject inherited development URL before any engine.
        settings = Settings(database_url=url, app_env='test', embedding_provider='gemini',
            embedding_model='gemini-embedding-001', embedding_dimensions=768,
            embedding_revision='retrieval-v1', llm_provider='gemini', llm_model='gemini-2.5-flash',
            embedding_provider_attempts=1, embedding_job_max_attempts=1, llm_max_attempts=1,
            llm_max_output_tokens=512, search_min_similarity=0, rag_min_similarity=0)
        control = create_engine(url, hide_parameters=True)
        with control.begin() as connection:
            connection.execute(CreateSchema(schema))
        created = True
        scratch = create_engine(url, hide_parameters=True,
            connect_args={'options': f'-c search_path={schema},public -c statement_timeout=15000'},
            execution_options={'schema_translate_map': {None: schema}})
        Base.metadata.create_all(scratch)
        transport = ProbeTransport()
        embedding = EmbeddingEngine(settings, GeminiEmbeddingProvider(settings, transport=transport, synthetic_only=True))
        generation = LLMEngine(settings, GeminiLLMProvider(settings, transport=transport, synthetic_only=True))
        with Session(scratch, expire_on_commit=False) as db:
            summary.update(exercise(db, settings, embedding, generation))
        summary['result'] = 'PASS'
    except Exception:
        # Never display provider bodies, request headers, SQL, settings or tracebacks.
        summary['reason'] = 'Configuration, provider or synthetic acceptance failed; no further provider calls made'
    finally:
        if transport:
            summary['requests'] = transport.counts
        if scratch:
            scratch.dispose()
        if created:
            try:
                with control.begin() as connection:
                    connection.execute(DropSchema(schema, cascade=True))
                summary['owned_schema_removed'] = True
            except Exception:
                summary['result'] = 'BLOCKED'
                summary['owned_schema_removed'] = False
        if control:
            control.dispose()
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
