"""Public document error vocabulary; parser internals never cross API boundaries."""
ERRORS = {
    'malformed': 'Malformed PDF', 'encrypted': 'Encrypted PDFs are not supported',
    'encoding': 'Text must be valid UTF-8', 'binary': 'File content does not match its extension',
    'empty': 'Document contains no text', 'ocr': 'Scanned or image-only PDF; OCR is not supported',
    'limits': 'Document exceeds parser resource limits', 'timeout': 'Document processing timed out',
}


class ParsingError(Exception):
    def __init__(self, code):
        self.code = code if code in ERRORS else 'malformed'
        super().__init__(ERRORS[self.code])


SAFE_PROCESSING_ERRORS = frozenset(ERRORS.values()) | {
    'Processing attempt limit reached', 'Original checksum mismatch',
    'Original storage unavailable', 'Document exceeds chunk limits', 'Document processing failed',
}
