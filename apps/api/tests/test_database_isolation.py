"""Test boundaries and real unqualified SQL must stay inside owned test data."""
import uuid
import pytest
from sqlalchemy import text
from database_guard import test_database_url as guarded_url
from test_workspace_concurrency import scratch_database


@pytest.mark.parametrize('value', ['', 'postgresql+psycopg://localhost:5433/evidenceai',
    'postgresql+psycopg://remote:5432/evidenceai_test_'+'a'*32,
    'postgresql+psycopg://localhost:5432/evidenceai_test_'+'a'*32+'?options=-csearch_path=public',
    'postgresql+psycopg://localhost/evidenceai_test_'+'a'*32])
def test_refuses_unsafe_database(value):
    with pytest.raises(RuntimeError): guarded_url({'EVIDENCEAI_TEST_DATABASE_URL':value})


def test_raw_and_orm_connections_are_disposable(connection):
    name=connection.scalar(text('select current_database()'))
    assert name.startswith('evidenceai_test_') and len(name)==48
    assert connection.scalar(text('select current_schema()')).startswith('test_suite_')
    assert connection.scalar(text("select count(*) from pg_namespace where nspname='public'"))==1


def test_concurrent_schema_raw_sql_is_scoped(scratch_database):
    schema=scratch_database.get_execution_options()['schema_translate_map'][None]
    with scratch_database.connect() as connection:
        assert connection.scalar(text('select current_schema()'))==schema
        assert connection.scalar(text('select count(*) from users'))==0


@pytest.mark.parametrize('module', ['evaluate_retrieval', 'evaluate_rag'])
def test_offline_evaluators_refuse_inherited_development_configuration(monkeypatch, module):
    from importlib import import_module
    monkeypatch.delenv('EVIDENCEAI_TEST_DATABASE_URL', raising=False)
    with pytest.raises(RuntimeError, match='Explicit loopback disposable'):
        import_module('app.'+module).evaluate()
