"""Content-free JSON events and bounded, process-local Prometheus instrumentation."""
import asyncio
from collections import defaultdict
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
import json
import logging
import math
import re
import threading
import time
from uuid import UUID, uuid4

from opentelemetry import trace
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, TimeoutError as PoolTimeout
from starlette.responses import JSONResponse

request_id = ContextVar('request_id', default=None)
BUCKETS = (.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10, 30, 60, 120, 300)
OPERATIONS = frozenset({'database', 'retrieval', 'embedding', 'generation', 'rag', 'extraction',
                        'chunking', 'cleanup', 'document_job', 'embedding_job', 'worker_tick'})


def valid_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', value))


def category(error=None, status=200):
    if isinstance(error, (DBAPIError, PoolTimeout)): return 'database'
    if isinstance(error, (TimeoutError, asyncio.TimeoutError)): return 'timeout'
    if isinstance(error, asyncio.CancelledError): return 'cancelled'
    if error:
        return {'LLMError':'provider','EmbeddingError':'provider','StorageError':'storage',
                'ParsingError':'parser','CitationError':'citation'}.get(type(error).__name__,'internal')
    if status == 429: return 'rate_limit'
    if status in (401, 403): return 'access'
    if status >= 500: return 'unavailable'
    if status >= 400: return 'request'
    return 'none'


class SafeJSONFormatter(logging.Formatter):
    def format(self, record):
        # No getMessage(), args, exception text, stack traces, SQL, URLs or arbitrary extras.
        data = {'timestamp': datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                'severity': record.levelname, 'operation': 'application', 'request_id': request_id.get()}
        safe = getattr(record, 'safe', {})
        if not isinstance(safe, dict): safe = {}
        allowed = {
            'operation': OPERATIONS | {'http_request','document_enqueued','document_claimed','document_finished',
                'embedding_enqueued','embedding_claimed','embedding_finished','worker_started','worker_stopped','worker_metrics_failed'},
            'error_category': {'none','database','timeout','cancelled','internal','rate_limit','access','unavailable','request','provider','storage','parser','citation'},
            'provider': {'none','disabled','fake','mock','openai','gemini'},
            'outcome': {'success','failure','answered','insufficient_evidence','retrieval_unavailable','provider_error','queued','running','done','failed'},
        }
        for key, values in allowed.items():
            value = safe.get(key)
            if isinstance(value, str) and value in values: data[key] = value
        for key in ('request_id', 'workspace_id', 'job_id'):
            try:
                if safe.get(key): data[key] = str(UUID(str(safe[key])))
            except (ValueError, TypeError): pass
        # Route templates are supplied only by the router, never a client path.
        route = safe.get('route')
        if isinstance(route, str) and len(route) <= 200 and re.fullmatch(r'[/a-zA-Z0-9_{}-]+', route): data['route'] = route
        for key in ('http_status', 'duration_ms', 'result_count'):
            value = safe.get(key)
            if isinstance(value, (int, float)) and math.isfinite(value): data[key] = value
        return json.dumps(data, separators=(',', ':'))


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(SafeJSONFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    # Uvicorn access logs contain raw paths; third-party messages are discarded too.
    for name in ('uvicorn', 'uvicorn.error', 'uvicorn.access', 'sqlalchemy.engine', 'httpx', 'httpcore'):
        log = logging.getLogger(name)
        log.handlers.clear()
        log.propagate = True


def emit(operation, **fields):
    logging.getLogger('evidenceai').info('event', extra={'safe': {'operation': operation, **fields}})


class Registry:
    """Fixed schema; values never become labels without validation at the boundary."""
    def __init__(self):
        self.lock = threading.Lock()
        self.counters = defaultdict(float)
        self.histograms = {}

    def count(self, name, labels=(), amount=1):
        if not math.isfinite(amount) or amount < 0: return
        with self.lock: self.counters[name, tuple(labels)] += amount

    def observe(self, name, labels, seconds):
        seconds = max(0, seconds)
        if not math.isfinite(seconds): return
        with self.lock:
            item = self.histograms.setdefault((name, tuple(labels)), [0, 0, [0]*len(BUCKETS)])
            item[0] += 1; item[1] += seconds
            for i, bound in enumerate(BUCKETS): item[2][i] += seconds <= bound

    def render(self):
        def sample(name, labels, value):
            suffix = '{' + ','.join(f'{key}={json.dumps(str(val))}' for key,val in labels) + '}' if labels else ''
            return f'evidenceai_{name}{suffix} {value}\n'
        with self.lock:
            output = []
            declared = set()
            for (name, labels), value in sorted(self.counters.items()):
                if name not in declared:
                    output.append(f'# HELP evidenceai_{name} Process-local {name.replace("_"," ")}.\n# TYPE evidenceai_{name} counter\n'); declared.add(name)
                output.append(sample(name, labels, value))
            for (name, labels), (count, total, buckets) in sorted(self.histograms.items()):
                if name not in declared:
                    output.append(f'# HELP evidenceai_{name} Process-local elapsed seconds with cumulative buckets.\n# TYPE evidenceai_{name} histogram\n'); declared.add(name)
                for bound, value in zip(BUCKETS, buckets): output.append(sample(name+'_bucket', labels+(('le',bound),), value))
                output.extend([sample(name+'_bucket',labels+(('le','+Inf'),),count),
                               sample(name+'_count',labels,count),sample(name+'_sum',labels,total)])
            return ''.join(output)


registry = Registry()


def measured(operation, provider=False):
    if operation not in OPERATIONS: raise ValueError('Unknown telemetry operation')
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            started, outcome = time.perf_counter(), 'success'
            kind = 'none'
            if provider:
                kind = getattr(args[0].settings, 'embedding_provider' if operation == 'embedding' else 'llm_provider')
                if kind not in {'disabled', 'fake', 'mock', 'openai', 'gemini'}: kind = 'none'
            with trace.get_tracer('evidenceai').start_as_current_span(operation, record_exception=False, set_status_on_exception=False):
                try:
                    result = fn(*args, **kwargs)
                    if operation == 'retrieval': registry.count('retrieval_results_total', amount=len(result))
                    return result
                except BaseException as error:
                    outcome = 'failure'
                    emit(operation, error_category=category(error), provider=kind)
                    raise
                finally:
                    labels = (('operation',operation),('outcome',outcome),('provider',kind))
                    registry.count('operations_total', labels)
                    registry.observe('operation_seconds', labels, time.perf_counter()-started)
                    emit(operation, outcome=outcome, provider=kind, duration_ms=round((time.perf_counter()-started)*1000, 3))
        return wrapped
    return decorate


class RequestTelemetryMiddleware:
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http': return await self.app(scope, receive, send)
        candidates = [v.decode('latin1') for k,v in scope['headers'] if k.lower() == b'x-request-id']
        identifier = candidates[0] if len(candidates) == 1 and valid_id(candidates[0]) else str(uuid4())
        token = request_id.set(identifier)
        started, status, failure, sent = time.perf_counter(), 500, None, False
        async def correlated_send(message):
            nonlocal status, sent
            if message['type'] == 'http.response.start':
                status, sent = message['status'], True
                headers = [(k,v) for k,v in message.get('headers',[]) if k.lower() not in {b'x-request-id', b'cache-control'}]
                message['headers'] = headers+[(b'x-request-id',identifier.encode()),(b'cache-control',b'no-store')]
            await send(message)
        # Do not extract untrusted remote traceparent/baggage; local spans are optional SDK hooks.
        try:
            with trace.get_tracer('evidenceai').start_as_current_span('http_request',record_exception=False,set_status_on_exception=False):
                await self.app(scope, receive, correlated_send)
        except asyncio.CancelledError as error:
            failure, status = error, 499
            raise
        except Exception as error:
            failure = error
            if sent: raise
            status = 503 if isinstance(error, (DBAPIError, PoolTimeout)) else 500
            await JSONResponse({'detail':'Service temporarily unavailable', 'request_id':identifier}, status_code=status)(scope, receive, correlated_send)
        finally:
            route = getattr(scope.get('route'), 'path', 'unmatched')
            method = scope.get('method') if scope.get('method') in {'GET','POST','PATCH','DELETE','HEAD','OPTIONS','PUT'} else 'OTHER'
            labels = (('route',route),('method',method),('status',str(status)))
            elapsed = time.perf_counter()-started
            registry.count('http_requests_total',labels)
            registry.observe('http_request_seconds',labels,elapsed)
            if status >= 400: registry.count('http_errors_total', (('category',category(failure,status)),))
            emit('http_request',route=route,http_status=status,duration_ms=round(elapsed*1000,3),error_category=category(failure,status))
            request_id.reset(token)


@event.listens_for(Engine, 'before_cursor_execute')
def before_query(conn, cursor, statement, parameters, context, executemany):
    context._telemetry_started = time.perf_counter()
    context._telemetry_span = trace.get_tracer('evidenceai').start_span('database')


@event.listens_for(Engine, 'after_cursor_execute')
def after_query(conn, cursor, statement, parameters, context, executemany):
    context._telemetry_span.end()
    registry.observe('operation_seconds', (('operation','database'),('outcome','success'),('provider','none')),
                     time.perf_counter()-context._telemetry_started)
    # Same correlation context as retrieval/generation; no query text or parameters.
    emit('database', duration_ms=round((time.perf_counter()-context._telemetry_started)*1000,3))


@event.listens_for(Engine, 'handle_error')
def query_failed(context):
    span = getattr(context.execution_context, '_telemetry_span', None)
    if span: span.end()
    registry.count('database_errors_total')
    emit('database',error_category='database')


def provider_call(operation, provider, function, *args, **kwargs):
    """One actual adapter attempt, distinct from engine-level calls/retries."""
    if operation not in {'embedding','generation'} or provider not in {'fake','mock','openai','gemini','disabled'}:
        raise ValueError('Unknown provider telemetry label')
    outcome='success'
    try:
        return function(*args,**kwargs)
    except BaseException:
        outcome='failure'
        raise
    finally:
        registry.count('provider_calls_total',(('operation',operation),('provider',provider),('outcome',outcome)))
