"""Fixed, credential-free configuration diagnostics. Never probes Google."""
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class GenerationCapabilities:
    thinking_level: str | None = None
    thought_signature: bool = False
    thought_tokens: bool = False
    sampling: bool = True
    quote_selection: bool = False


# Only explicitly reviewed REST contracts are admitted. There is no model fallback.
GENERATION_MODELS = MappingProxyType({
    'gemini-2.5-flash': GenerationCapabilities(),
    'gemini-3.5-flash-lite': GenerationCapabilities(
        thinking_level='minimal', thought_signature=True, thought_tokens=True, sampling=False,
        quote_selection=True),
})


MESSAGES = {
    'api_key_missing': 'Configure GEMINI_API_KEY privately in the backend environment.',
    'live_requests_blocked': 'Live Gemini requests are blocked pending explicit approval.',
    'free_tier_not_confirmed': 'Confirm this project has free access and quota for both operations.',
    'data_transfer_not_authorized': 'Gemini data-use consent is not configured.',
    'private_document_transfer_not_authorized': 'Private document transfer requires separate approval.',
    'hosted_provider_not_authorized': 'Enable the selected hosted provider only after approval.',
    'environment_not_allowed': 'Gemini is restricted to local development and test environments.',
}


def blocker(settings, kind, *, synthetic_only=False):
    if settings.app_env not in {'development', 'test'}:
        return 'environment_not_allowed'
    if not settings.gemini_api_key or not settings.gemini_api_key.get_secret_value().strip():
        return 'api_key_missing'
    for allowed, code in (
        (settings.gemini_live_requests_allowed, 'live_requests_blocked'),
        (settings.gemini_free_tier_confirmed, 'free_tier_not_confirmed'),
        (settings.gemini_data_transfer_allowed, 'data_transfer_not_authorized'),
        (synthetic_only or settings.gemini_private_documents_allowed, 'private_document_transfer_not_authorized'),
        (getattr(settings, kind+'_hosted_allowed'), 'hosted_provider_not_authorized'),
    ):
        if not allowed:
            return code
    return None
