"""Offline grounded-answer benchmark using actual PostgreSQL indexing and retrieval.

Only a uniquely named disposable schema is created and dropped. No public rows,
source files, provider keys or hosted APIs are involved.
"""

import argparse
import hashlib
import json
import statistics
import time
import uuid
from contextlib import nullcontext
from unittest.mock import patch
from fastapi import HTTPException
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_engine
from app.models import Document, DocumentChunk, User, Workspace, WorkspaceMember
from app.schemas.ask import AskRequest
from app.services import embedding_jobs, rag_service
from app.services.llm_providers import LLMReply, LLMError

DATASET = Path(__file__).resolve().parents[1] / "evaluation" / "grounded_answers.json"


class AdversarialEngine:
    """Deliberate invalid outputs test the post-generation validator independently."""

    def __init__(self, settings, attack):
        self.settings, self.attack = settings, attack

    def generate(self, prompt, *, deadline):
        if self.attack in {'outage','timeout'}:
            raise LLMError('timeout' if self.attack == 'timeout' else 'unavailable')
        if self.attack == 'numerical':
            return LLMReply({'outcome':'answered','claims':[{'text':'Solar panel warranty lasts 90 years.',
                'supports':[{'citation_id':'C1','quote':'Solar panel warranty lasts 10 years.'}]}]},self.settings.llm_model)
        text = "Solar panels convert sunlight into renewable electricity."
        if self.attack == "claim":
            text = "Solar panels convert moonlight into renewable electricity."
        citation_id = "C99" if self.attack == "reference" else "C1"
        return LLMReply(
            {
                "outcome": "answered",
                "claims": [
                    {
                        "text": text,
                        "supports": [{"citation_id": citation_id, "quote": text}],
                    }
                ],
            },
            self.settings.llm_model,
        )


def evaluate(dataset_path=DATASET, *, extended=False):
    dataset = json.loads(Path(dataset_path).read_text())
    if extended:
        dataset['documents'].append({'id':'misleading','text':'The proposed audit retention period is 90 days. Approved audit retention period is 30 days.'})
        dataset['cases'].extend([
            {'id':'misleading-planned-versus-approved','question':'Approved audit retention period','documents':['misleading'],'status':'answered','expected_claim':'Approved audit retention period is 30 days.','support_document':'misleading'},
            {'id':'provider-outage','question':'What do solar panels convert?','documents':['solar'],'attack':'outage','status':'provider_error'},
            {'id':'provider-timeout','question':'What do solar panels convert?','documents':['solar'],'attack':'timeout','status':'provider_error'},
            {'id':'retrieval-outage','question':'What do solar panels convert?','documents':['solar'],'attack':'retrieval','status':'retrieval_unavailable'},
            {'id':'unsupported-numerical-claim','question':'Solar panel warranty','documents':['warranty'],'attack':'numerical','status':'provider_error'},
        ])
    # Explicitly isolate provider configuration from any developer .env choices.
    settings = Settings(
        app_env="test",
        auth_allow_insecure_http=True,
        trusted_frontend_origins=["http://localhost:3000"],
        embedding_provider="fake",
        embedding_model="fake-hash-v1",
        embedding_revision="1",
        embedding_dimensions=128,
        embedding_hosted_allowed=False,
        openai_api_key=None,
        embedding_batch_size=16,
        embedding_input_max_bytes=8000,
        embedding_http_timeout_seconds=10,
        embedding_request_budget_seconds=30,
        embedding_provider_attempts=3,
        embedding_job_max_attempts=3,
        embedding_job_lease_seconds=120,
        llm_provider="mock",
        llm_model="mock-extractive-v1",
        llm_revision="1",
        llm_hosted_allowed=False,
        llm_temperature=None,
        llm_temperature_supported=False,
        llm_max_output_tokens=1000,
        llm_timeout_seconds=15,
        llm_max_attempts=2,
        rag_request_timeout_seconds=45,
        rag_retrieval_limit=6,
        rag_min_similarity=0.25,
        rag_context_token_budget=4096,
        rag_input_token_budget=12000,
        rag_max_claims=4,
        rag_concurrent_generations=4,
    )
    engine = get_engine()
    schema = "eval_rag_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    scratch = create_engine(
        get_settings().database_url.get_secret_value(),
        hide_parameters=True,
        execution_options={"schema_translate_map": {None: schema}},
    )
    try:
        Base.metadata.create_all(scratch)
        with sessionmaker(scratch, expire_on_commit=False)() as db:
            owner = User(
                email=f"{uuid.uuid4()}@example.com", display_name="Synthetic evaluation"
            )
            db.add(owner)
            db.flush()
            workspace = Workspace(name="Synthetic RAG evaluation", owner_id=owner.id)
            db.add(workspace)
            db.flush()
            db.add(
                WorkspaceMember(
                    workspace_id=workspace.id, user_id=owner.id, role="owner"
                )
            )
            mapping = {}
            for record in dataset["documents"]:
                document = Document(
                    workspace_id=workspace.id,
                    uploaded_by=owner.id,
                    original_filename=record["id"] + ".txt",
                    storage_key=uuid.uuid4().hex,
                    checksum_sha256=hashlib.sha256(record["text"].encode()).hexdigest(),
                    mime_type="text/plain",
                    file_size=len(record["text"].encode()),
                    processing_status="completed",
                )
                db.add(document)
                db.flush()
                db.add(
                    DocumentChunk(
                        document_id=document.id,
                        workspace_id=workspace.id,
                        chunk_index=0,
                        text=record["text"],
                        page_number=1,
                        section="Synthetic",
                        source_ref=f"document:{document.id}/page:1",
                        char_start=0,
                        char_end=len(record["text"]),
                    )
                )
                db.flush()
                mapping[record["id"]] = document.id
                embedding_jobs.enqueue(db, document, settings)
            db.commit()
            while embedding_jobs.run_once(db, settings):
                pass
            chunks = {
                str(chunk.id): chunk
                for chunk in db.scalars(select(DocumentChunk)).all()
            }
            details, latencies = [], []
            correct = emitted_claims = supported = citation_count = valid_citations = (
                gold_support
            ) = 0
            expected_insufficient = detected_insufficient = 0
            for case in dataset["cases"]:
                started = time.perf_counter()
                failure = patch('app.services.search_service.search',side_effect=HTTPException(503,'Synthetic retrieval outage')) if case.get('attack') == 'retrieval' else nullcontext()
                with failure:
                    body = rag_service.ask(
                        db,
                        workspace.id,
                        owner.id,
                        AskRequest(
                            question=case["question"],
                            document_ids=[mapping[key] for key in case["documents"]],
                        ),
                        settings,
                        engine=AdversarialEngine(settings, case["attack"])
                        if "attack" in case and case["attack"] != "retrieval"
                        else None,
                    ).body
                latency = (time.perf_counter() - started) * 1000
                latencies.append(latency)
                exact = body.status == case["status"]
                if case["status"] == "answered":
                    exact = exact and [claim.text for claim in body.claims] == [
                        case["expected_claim"]
                    ]
                correct += exact
                if case["status"] == "insufficient_evidence":
                    expected_insufficient += 1
                    detected_insufficient += body.status == "insufficient_evidence"
                by_id = {citation.citation_id: citation for citation in body.citations}
                for citation in body.citations:
                    citation_count += 1
                    chunk = chunks.get(str(citation.chunk_id))
                    valid_citations += bool(
                        chunk
                        and chunk.document_id == citation.document_id
                        and chunk.workspace_id == workspace.id
                        and citation.document_id
                        in [mapping[key] for key in case["documents"]]
                        and citation.supporting_excerpt in chunk.text
                    )
                for claim in body.claims:
                    emitted_claims += 1
                    supported += all(
                        identifier in by_id
                        and claim.text in by_id[identifier].supporting_excerpt
                        for identifier in claim.citation_ids
                    ) and bool(claim.citation_ids)
                    gold_support += bool(
                        case.get("expected_claim") == claim.text
                        and claim.citation_ids
                        and all(
                            by_id[identifier].document_id
                            == mapping[case["support_document"]]
                            for identifier in claim.citation_ids
                        )
                    )
                details.append(
                    {
                        "id": case["id"],
                        "expected_status": case["status"],
                        "actual_status": body.status,
                        "reason": body.reason,
                        "correct": bool(exact),
                        "latency_ms": round(latency, 4),
                    }
                )
            guards=[]
            if extended:
                foreign_user=User(email=f'{uuid.uuid4()}@example.com',display_name='Synthetic outsider')
                db.add(foreign_user);db.flush()
                foreign=Workspace(name='Synthetic foreign',owner_id=foreign_user.id)
                db.add(foreign);db.flush();db.commit()
                for name, target, filters in [('cross-workspace',foreign.id,None),('deleted-reference',workspace.id,[mapping['backup']])]:
                    if name == 'deleted-reference':
                        from app.services.document_service import delete_document
                        db.rollback()
                        delete_document(db,workspace.id,mapping['backup'],owner.id)
                    try:
                        rag_service.ask(db,target,owner.id,AskRequest(question='backup storage region',document_ids=filters),settings)
                        passed=False
                    except HTTPException as error:
                        passed=error.status_code==404
                    guards.append({'id':name,'correct':passed,'expected_status':404})
            return {
                'guards':guards,
                "dataset": dataset["name"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "method": "Real PostgreSQL fake-hash retrieval + mock extractive generation; hand-authored exact claim/source gold labels; deliberate adversarial validation and failure cases",
                "limitations": f"{len(details)} English synthetic cases; lexical providers and exact quotes; no hosted, semantic entailment, representative corpus, load or independent security evaluation",
                "case_count": len(details),
                "correct_cases": correct,
                "answer_correctness": correct / len(details),
                "emitted_claim_count": emitted_claims,
                "citation_count": citation_count,
                "citation_reference_validity": valid_citations / citation_count
                if citation_count
                else None,
                "citation_gold_support_quality": gold_support / emitted_claims
                if emitted_claims
                else None,
                "unsupported_claim_frequency": (emitted_claims - supported)
                / emitted_claims
                if emitted_claims
                else None,
                "expected_insufficient_count": expected_insufficient,
                "detected_insufficient_count": detected_insufficient,
                "insufficient_evidence_recall": detected_insufficient
                / expected_insufficient
                if expected_insufficient
                else None,
                "latency_mean_ms": round(statistics.mean(latencies), 4),
                "latency_median_ms": round(statistics.median(latencies), 4),
                "latency_p95_ms": round(
                    sorted(latencies)[max(0, int(len(latencies) * 0.95 + 0.999) - 1)], 4
                ),
                "cases": details,
            }
    finally:
        scratch.dispose()
        assert schema.startswith("eval_rag_") and len(schema) == 41
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate synthetic grounded answers in a disposable PostgreSQL schema"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    serialized = json.dumps(evaluate(), indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized)
    print(serialized, end="")


if __name__ == "__main__":
    main()
