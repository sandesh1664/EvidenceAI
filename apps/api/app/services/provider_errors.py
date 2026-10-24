"""Allowlisted public diagnostics; raw provider errors never cross this boundary."""
from app.services.gemini_configuration import MESSAGES

EMBEDDING_ERRORS = {
    'Gemini API key is invalid': ('embedding_invalid_key', 'The Gemini API key was rejected. Check the backend key privately.'),
    'Gemini embedding model is unavailable': ('embedding_model_unavailable', 'The embedding model is unavailable to this project. Check model access; no alternative was selected.'),
    'Gemini project access is denied': ('embedding_access_denied', 'Gemini denied project access. Check API restrictions and model permissions.'),
    'Embedding provider quota exhausted': ('embedding_quota', 'The Gemini embedding quota is exhausted. Automatic retries stopped; verify free quota before retrying.'),
}
for code, message in MESSAGES.items():
    EMBEDDING_ERRORS[message] = ('embedding_'+code, message)
PUBLIC_EMBEDDING_MESSAGES = dict(EMBEDDING_ERRORS.values())
GENERATION_MESSAGES = {
    'invalid_key': 'The Gemini API key was rejected. Check the backend key privately.',
    'model_unavailable': 'The generation model is unavailable to this project. No alternative was selected.',
    'access_denied': 'Gemini denied project access. Check API restrictions and model permissions.',
    'quota': 'The Gemini generation quota is exhausted. Automatic retries stopped; verify free quota before retrying.',
    'configuration': 'Gemini requests are blocked by local configuration or consent. Check Research readiness or run the local configuration doctor.',
}
