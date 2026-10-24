from app.core.telemetry import measured
import codecs
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unicodedata

import psutil

from app.core.config import Settings
from app.core.document_errors import ParsingError
from app.services.document_storage import DocumentStorage

MIME_TYPES = {'.pdf': 'application/pdf', '.txt': 'text/plain', '.md': 'text/markdown'}


def validate_filename(name: str | None):
    if (not name or len(name) > 255 or name != name.strip() or '..' in name
            or any(c in name for c in '/\\:')
            or any(unicodedata.category(c).startswith('C') for c in name)):
        raise ValueError('Unsafe filename')
    extension = Path(name).suffix.lower()
    if extension not in MIME_TYPES:
        raise ValueError('Unsupported file format')
    return extension


def validate_text(stream):
    decoder = codecs.getincrementaldecoder('utf-8-sig')('strict')
    try:
        while data := stream.read(65536):
            text = decoder.decode(data)
            if any(ord(c) < 32 and c not in '\n\r\t\f' for c in text):
                raise ParsingError('binary')
        decoder.decode(b'', final=True)
    except UnicodeDecodeError:
        raise ParsingError('encoding') from None


@measured("extraction")
def run_parser(stream, extension: str, settings: Settings, *, validate_only=False):
    timeout = settings.document_validation_timeout if validate_only else settings.document_processing_timeout
    options = dict(layout=settings.document_pdf_layout, pages=settings.document_max_pages, chars=settings.document_max_text_chars,
                   memory=settings.document_parser_memory_mb, seconds=timeout,
                   bytes=settings.document_upload_max_bytes)
    output_limit = settings.document_max_text_chars * 12 + 1024 * 1024
    # Buffered readers can satisfy seek(0) without rewinding the underlying fd.
    # The child reads that descriptor, so rewind both layers explicitly.
    stream.seek(0)
    os.lseek(stream.fileno(), 0, os.SEEK_SET)
    with tempfile.TemporaryFile() as output:
        try:
            process = subprocess.Popen([sys.executable, '-I', str(Path(__file__).with_name('document_parser_child.py')),
                'validate' if validate_only else 'extract', extension, json.dumps(options)],
                stdin=stream, stdout=output, stderr=subprocess.DEVNULL,
                env={'PATH': '', 'LANG': 'C.UTF-8'})
            deadline = time.monotonic() + timeout
            try:
                try:
                    monitored = psutil.Process(process.pid)
                except psutil.NoSuchProcess:
                    monitored = None
                while process.poll() is None:
                    if time.monotonic() >= deadline:
                        raise ParsingError('timeout')
                    try:
                        if monitored is not None and monitored.memory_info().rss > settings.document_parser_memory_mb * 1024 * 1024:
                            raise ParsingError('limits')
                    except psutil.NoSuchProcess:
                        pass
                    try:
                        process.wait(timeout=min(0.02, max(0.001, deadline-time.monotonic())))
                    except subprocess.TimeoutExpired:
                        pass
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
        except OSError:
            raise ParsingError('limits') from None
        if process.returncode != 0:
            raise ParsingError('limits')
        output.seek(0)
        raw = output.read(output_limit + 1)
        if len(raw) > output_limit:
            raise ParsingError('limits')
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ParsingError('limits') from None
    if 'error' in data:
        raise ParsingError(data['error'])
    return data['sources']


def validate_upload(storage: DocumentStorage, key: str, extension: str, browser_mime: str | None, settings: Settings):
    declared = (browser_mime or 'application/octet-stream').split(';', 1)[0].lower()
    allowed = {MIME_TYPES[extension], 'application/octet-stream'}
    if extension == '.md':
        allowed.add('text/plain')
    if declared not in allowed:
        raise ParsingError('binary')
    with storage.open(key, staged=True) as stream:
        head = stream.read(16)
        stream.seek(0)
        if extension == '.pdf':
            if not head.startswith(b'%PDF-'):
                raise ParsingError('binary')
            run_parser(stream, extension, settings, validate_only=True)
        else:
            if head.startswith((b'%PDF-', b'PK\x03\x04', b'\x89PNG', b'\xff\xd8', b'\x1f\x8b', b'\x7fELF', b'MZ')):
                raise ParsingError('binary')
            validate_text(stream)
