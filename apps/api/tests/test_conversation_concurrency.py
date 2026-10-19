"""Independent PostgreSQL sessions exercise in-flight turn races via real cookie HTTP."""

# ruff: noqa: F401,F811
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_embeddings import seed_completed
from test_workspace_concurrency import concurrent_api, scratch_database

from app.core.config import get_settings
from app.main import app
from app.models import Message, MessageCitation, Workspace, WorkspaceMember
from app.services import embedding_jobs, rag_service
from app.services.llm_providers import MockLLMProvider

QUESTION = "What do solar panels convert?"
TEXT = "Solar panels convert sunlight into renewable electricity."


@pytest.fixture
def in_flight(concurrent_api, monkeypatch):
    _engine, factory, people, workspace_id, request = concurrent_api
    settings = app.dependency_overrides[get_settings]()
    settings.embedding_provider = "fake"
    settings.llm_provider = "mock"
    settings.rag_min_similarity = 0.0
    with factory() as db:
        workspace = db.get(Workspace, workspace_id)
        document = seed_completed(db, workspace, people["owner"])
        document_id = document.id
        embedding_jobs.enqueue(db, document, settings)
        db.commit()
        while embedding_jobs.run_once(db, settings):
            pass
    entered, release = Event(), Event()
    calls = []

    class BlockingEngine:
        def __init__(self, settings):
            self.settings = settings

        def generate(self, prompt, *, deadline):
            calls.append(prompt)
            entered.set()
            assert release.wait(10), "Test did not release generation"
            return MockLLMProvider(self.settings).generate(prompt, timeout=1)

    monkeypatch.setattr(rag_service, "LLMEngine", BlockingEngine)
    created = request(
        "owner", "POST", "/conversations", {"title": "Concurrent research"}
    )
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]
    suffix = f"/conversations/{conversation_id}/messages"
    try:
        yield (
            factory,
            people,
            request,
            document_id,
            conversation_id,
            suffix,
            entered,
            release,
            calls,
        )
    finally:
        release.set()


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_submission_replays_pending_or_conflicts(in_flight, same_key):
    factory, _people, request, _document_id, _cid, suffix, entered, release, calls = (
        in_flight
    )
    data = {"question": QUESTION, "idempotency_key": str(uuid4())}
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(request, "owner", "POST", suffix, data)
        assert entered.wait(5)
        # Generation holds no workspace/conversation transaction: these reads and
        # competing POSTs finish before the first provider call is released.
        pending = request("owner", "GET", suffix, None)
        assert (
            pending.status_code == 200
            and pending.json()["items"][1]["generation_status"] == "pending"
        )
        other = data if same_key else data | {"idempotency_key": str(uuid4())}
        second = executor.submit(request, "owner", "POST", suffix, other).result(
            timeout=5
        )
        assert second.status_code == (202 if same_key else 409), second.text
        assert second.headers["Retry-After"] == "2"
        release.set()
        final = first.result(timeout=5)
    assert final.status_code == 201, final.text
    assert final.json()["assistant_message"]["answer_status"] == "answered"
    assert len(calls) == 1
    replay = request("owner", "POST", suffix, data)
    assert (
        replay.status_code == 200
        and replay.json()["assistant_message"] == final.json()["assistant_message"]
    )
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Message)) == 2
        assert db.scalar(select(func.count()).select_from(MessageCitation)) == 1
    next_turn = request(
        "owner", "POST", suffix, data | {"idempotency_key": str(uuid4())}
    )
    assert (
        next_turn.status_code == 201
        and next_turn.json()["user_message"]["sequence"] == 3
    )


@pytest.mark.parametrize(
    "change", ["delete_conversation", "delete_source", "archive", "revoke_membership"]
)
def test_lifecycle_and_revocation_while_generation_runs(in_flight, change):
    factory, people, request, document_id, cid, suffix, entered, release, _calls = (
        in_flight
    )
    data = {"question": QUESTION, "idempotency_key": str(uuid4())}
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending = executor.submit(request, "owner", "POST", suffix, data)
        assert entered.wait(5)
        if change == "delete_conversation":
            response = request("owner", "DELETE", f"/conversations/{cid}", None)
            assert response.status_code == 204, response.text
        elif change == "delete_source":
            response = request("owner", "DELETE", f"/documents/{document_id}", None)
            assert response.status_code == 204, response.text
        elif change == "archive":
            response = request(
                "owner", "PATCH", f"/conversations/{cid}", {"archived": True}
            )
            assert response.status_code == 200, response.text
        else:
            # Authorized administrative membership changes use the workspace lock;
            # direct scratch-only removal simulates revocation by another worker.
            with factory() as writer:
                writer.execute(
                    WorkspaceMember.__table__.delete().where(
                        WorkspaceMember.user_id == people["owner"]
                    )
                )
                writer.commit()
        release.set()
        response = pending.result(timeout=5)
    if change in {"delete_conversation", "revoke_membership"}:
        assert response.status_code == 404, response.text
    else:
        assert response.status_code == 201, response.text
        assistant = response.json()["assistant_message"]
        assert assistant["answer_status"] == (
            "answered" if change == "archive" else "insufficient_evidence"
        )
        if change == "delete_source":
            assert not assistant["citations"] and not assistant["claims"]
    with factory() as db:
        if change == "delete_conversation":
            assert db.scalar(select(func.count()).select_from(Message)) == 0
        if change == "revoke_membership":
            assistant = db.scalar(select(Message).where(Message.role == "assistant"))
            assert (
                assistant.generation_status == "failed"
                and assistant.reason == "generation_interrupted"
            )
            assert "Solar panels" not in assistant.content
