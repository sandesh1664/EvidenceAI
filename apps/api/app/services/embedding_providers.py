"""Provider implementations contain no DB access and never expose raw provider errors."""
from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real
import re
import time
from typing import Protocol

import httpx

from app.core.config import Settings


class EmbeddingError(Exception):
    def __init__(self, message='Embedding provider unavailable', *, transient=False, retry_after=0):
        # Messages are from server code only; provider response bodies are never included.
        super().__init__(message)
        self.transient = transient
        self.retry_after = min(5,max(0,retry_after))


@dataclass(frozen=True)
class Profile:
    id: str
    provider: str
    model: str
    revision: str
    dimensions: int

    @property
    def identifier(self):
        return f'{self.provider}:{self.model}@{self.revision}/{self.dimensions}'


def profile_for(settings: Settings):
    values = (settings.embedding_provider,settings.embedding_model,settings.embedding_revision,settings.embedding_dimensions)
    key = hashlib.sha256(json.dumps(values,separators=(',',':')).encode()).hexdigest()
    return Profile(key,*values)


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str], *, timeout: float) -> list[list[float]]: ...


def validated_vectors(vectors, count, dimensions):
    if not isinstance(vectors,(list,tuple)) or len(vectors) != count:
        raise EmbeddingError('Invalid embedding provider output')
    normalized = []
    for vector in vectors:
        if not isinstance(vector,(list,tuple)) or len(vector) != dimensions:
            raise EmbeddingError('Invalid embedding vector dimensions')
        try:
            valid = all(not isinstance(v,bool) and isinstance(v,Real) and math.isfinite(v) for v in vector)
            norm = math.hypot(*vector) if valid else 0
        except (OverflowError,TypeError,ValueError):
            valid,norm = False,0
        if not valid:
            raise EmbeddingError('Embedding vectors must contain finite numbers')
        if not math.isfinite(norm) or norm <= 0:
            raise EmbeddingError('Embedding vectors must be nonzero')
        normalized.append([float(v/norm) for v in vector])
    return normalized


class FakeEmbeddingProvider:
    """Versioned signed token hashing. A lexical test double, not a semantic model."""
    def __init__(self, dimensions):
        self.dimensions = dimensions

    def embed(self,texts,*,timeout=10):
        result = []
        stops = {'a','an','the','is','are','of','to','and','in','for','on','with','what','how','does'}
        for text in texts:
            tokens = [token for token in re.findall(r'\w+',text.casefold()) if token not in stops]
            if not tokens:
                tokens = [text.casefold()]
            vector = [0.0]*self.dimensions
            for token in tokens:
                digest = hashlib.sha256(token.encode()).digest()
                vector[int.from_bytes(digest[:4],'big')%self.dimensions] += 1 if digest[4]%2 else -1
            # Hash cancellation is possible; deterministic nonzero fallback.
            if not any(vector):
                vector[int.from_bytes(hashlib.sha256(text.encode()).digest()[:4],'big')%self.dimensions] = 1
            result.append(vector)
        return validated_vectors(result,len(texts),self.dimensions)


class OpenAIEmbeddingProvider:
    endpoint = 'https://api.openai.com/v1/embeddings'

    def __init__(self,settings: Settings,*,transport=None):
        self.settings, self.transport = settings, transport

    def embed(self,texts,*,timeout):
        settings = self.settings
        if not settings.embedding_hosted_allowed or not settings.openai_api_key:
            raise EmbeddingError('Hosted embeddings are not configured')
        try:
            with httpx.Client(timeout=timeout,transport=self.transport,trust_env=False,follow_redirects=False) as client:
                with client.stream('POST',self.endpoint,headers={
                    'Authorization':'Bearer '+settings.openai_api_key.get_secret_value()},json={
                    'model':settings.embedding_model,'dimensions':settings.embedding_dimensions,
                    'encoding_format':'float','input':texts}) as response:
                    if response.status_code == 429 or response.status_code >= 500:
                        try: retry_after = float(response.headers.get('Retry-After','0'))
                        except ValueError: retry_after = 0
                        raise EmbeddingError('Embedding provider temporarily unavailable',transient=True,retry_after=retry_after)
                    if response.status_code != 200:
                        raise EmbeddingError('Embedding provider rejected the request')
                    maximum = len(texts)*settings.embedding_dimensions*32+8192
                    body = bytearray()
                    for data in response.iter_bytes():
                        body.extend(data)
                        if len(body)>maximum:
                            raise EmbeddingError('Invalid embedding provider output')
            payload = json.loads(body)
            if payload.get('model') != settings.embedding_model:
                raise EmbeddingError('Embedding model identity mismatch')
            items = payload['data']
            if (not isinstance(items,list) or len(items) != len(texts)
                    or any(type(item.get('index')) is not int for item in items)
                    or sorted(item['index'] for item in items) != list(range(len(texts)))):
                raise EmbeddingError('Invalid embedding provider output')
            return [item['embedding'] for item in sorted(items,key=lambda item:item['index'])]
        except httpx.TimeoutException:
            raise EmbeddingError('Embedding provider timed out',transient=True) from None
        except httpx.HTTPError:
            raise EmbeddingError('Embedding provider unavailable',transient=True) from None
        except (ValueError,KeyError,TypeError,AttributeError):
            raise EmbeddingError('Invalid embedding provider output') from None


def provider_for(settings):
    if settings.embedding_provider == 'fake':
        return FakeEmbeddingProvider(settings.embedding_dimensions)
    if settings.embedding_provider == 'openai':
        return OpenAIEmbeddingProvider(settings)
    raise EmbeddingError('Embedding provider is disabled')


class EmbeddingEngine:
    def __init__(self,settings: Settings,provider=None,*,sleep=time.sleep):
        self.settings, self.profile = settings, profile_for(settings)
        self.provider = provider if provider is not None else provider_for(settings)
        self.sleep = sleep

    def embed(self,texts):
        settings = self.settings
        if not isinstance(texts,list) or not texts or len(texts)>settings.embedding_batch_size:
            raise EmbeddingError('Invalid embedding batch')
        if any(not isinstance(t,str) or not t.strip() or '\x00' in t or len(t.encode('utf-8'))>settings.embedding_input_max_bytes for t in texts):
            raise EmbeddingError('Embedding input exceeds limits or is empty')
        deadline = time.monotonic()+settings.embedding_request_budget_seconds
        for attempt in range(settings.embedding_provider_attempts):
            try:
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise EmbeddingError('Embedding provider timed out',transient=True)
                result = self.provider.embed(texts,timeout=min(settings.embedding_http_timeout_seconds,remaining))
                return validated_vectors(result,len(texts),settings.embedding_dimensions)
            except EmbeddingError as error:
                if not error.transient or attempt+1 >= settings.embedding_provider_attempts:
                    raise
                pause = max(error.retry_after,min(4,0.5*2**attempt))
                if time.monotonic()+pause >= deadline:
                    raise EmbeddingError('Embedding provider timed out',transient=True) from None
                self.sleep(pause)
            except Exception:
                raise EmbeddingError('Embedding provider failed') from None
