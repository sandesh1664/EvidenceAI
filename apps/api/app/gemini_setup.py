"""Local configuration doctor: no HTTP requests, DB connection, or credential output."""
import json
import os
from dotenv import dotenv_values
from app.core.config import Settings, BACKEND_ROOT
from app.services.research_readiness import provider_status
from app.services.embedding_providers import profile_for


def main():
    values = dotenv_values(BACKEND_ROOT/'.env')
    key_present = bool(os.environ.get('GEMINI_API_KEY', values.get('GEMINI_API_KEY', '')))
    try:
        settings = Settings()
    except Exception:
        print(json.dumps({'status':'BLOCKED','gemini_key_configured':key_present,
            'message': 'Invalid backend settings. Check model IDs, dimensions, key presence and consent flags using docs/document-qa-setup.md. No provider was contacted.'}))
        return 1
    states = {kind:provider_status(settings, kind) for kind in ('embedding','llm')}
    print(json.dumps({'status':'CONFIGURATION ONLY; live access NOT VERIFIED',
        'gemini_key_configured':key_present, 'embedding_profile':profile_for(settings).identifier,
        'providers':states, 'live_requests_made':0}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
