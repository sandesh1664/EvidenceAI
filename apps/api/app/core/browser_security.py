from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from app.core.config import get_settings


class BrowserSecurityMiddleware:
    """Lazy settings preserve configuration-independent health checks."""
    def __init__(self, app):
        self.app = app
        self.cors = None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] == "/api/v1/health":
            return await self.app(scope, receive, send)
        settings = get_settings()
        if self.cors is None:
            self.cors = CORSMiddleware(self.protected, allow_origins=settings.trusted_frontend_origins,
                allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE"],
                allow_headers=["Content-Type", "X-CSRF-Protection"])
        await self.cors(scope, receive, send)

    async def protected(self, scope, receive, send):
        settings = get_settings()
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        origin = headers.get("origin")
        error = None
        if origin is not None and origin not in settings.trusted_frontend_origins:
            error = "Untrusted origin"
        if scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            if origin not in settings.trusted_frontend_origins or headers.get("x-csrf-protection") != "1":
                error = "CSRF validation failed"
            if settings.secure_cookies and scope["scheme"] != "https":
                error = "HTTPS required"
        if error:
            return await JSONResponse({"detail": error}, status_code=403)(scope, receive, send)
        async def secure_send(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((b"cache-control", b"no-store"))
            await send(message)
        upload = scope["method"] == "POST" and scope["path"].rstrip("/").endswith("/documents")
        if upload:
            from starlette.exceptions import HTTPException
            maximum = settings.document_upload_max_bytes + 65536  # bounded multipart envelope
            try:
                if int(headers.get("content-length", "0")) > maximum:
                    return await JSONResponse({"detail": "Upload body exceeds byte limit"}, status_code=413)(scope, receive, send)
            except ValueError:
                return await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(scope, receive, send)
            received = 0
            original_receive = receive
            async def limited_receive():
                nonlocal received
                message = await original_receive()
                if message["type"] == "http.request":
                    received += len(message.get("body", b""))
                    if received > maximum:
                        raise HTTPException(413, "Upload body exceeds byte limit")
                return message
            receive = limited_receive
        await self.app(scope, receive, secure_send)
