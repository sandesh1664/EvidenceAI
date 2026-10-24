"""Opt-in real TLS SMTP fixture; only imported by the guarded E2E server."""
from contextlib import contextmanager
from email import policy
from email.parser import BytesParser
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
from threading import Thread


@contextmanager
def delivery(settings, mail):
    from app.services import registration_service
    spec = importlib.util.spec_from_file_location('audit_local_mail', Path(__file__).resolve().parents[3] / 'infra/development/mail.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    directory = mail / 'smtp'
    module.initialize(directory)
    original = registration_service.deliver
    with module.Server(directory, port=0) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        settings.registration_email_enabled = True
        settings.smtp_host = '127.0.0.1'
        settings.smtp_port = server.server_address[1]
        settings.smtp_sender = 'noreply@evidenceai.test'
        settings.smtp_ca_file = directory / 'ca.pem'
        # The isolated browser uses manual proof entry on :3100. Keep the trusted
        # HTTPS email origin separate; never relax the local :3000 origin policy.
        settings.trusted_frontend_origins.append(settings.registration_public_origin)
        type(settings).model_validate(settings.model_dump())
        receipts = 0
        def received_delivery(settings, email, token):
            nonlocal receipts
            before = set(directory.glob('*.eml'))
            result = original(settings, email, token)
            received = set(directory.glob('*.eml')) - before
            if len(received) != 1:
                raise RuntimeError('Expected one real TLS receipt')
            message = BytesParser(policy=policy.default).parsebytes(received.pop().read_bytes())
            if str(message['To']) != email:
                raise RuntimeError('Receipt recipient mismatch')
            match = re.search(r'#token=([A-Za-z0-9_-]{43})', message.get_content())
            if not match or match.group(1) != token:
                raise RuntimeError('Receipt proof mismatch')
            target = mail / (hashlib.sha256(email.encode()).hexdigest() + '.json')
            with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as stream:
                json.dump({'token': match.group(1)}, stream)
            receipts += 1
            return result
        registration_service.deliver = received_delivery
        try:
            yield
        finally:
            registration_service.deliver = original
            server.shutdown()
            thread.join(timeout=12)
            print(json.dumps({"real_tls_smtp_receipts": receipts}), flush=True)
