from fastapi import FastAPI

app = FastAPI(
    title="EvidenceAI API",
    version="1.0.0",
    description="EvidenceAI Knowledge and Research Platform"
)

@app.get("/api/v1/health")
def health_check():
    return {
        "service": "EvidenceAI API",
        "status": "healthy",
        "version": "1.0.0"
    }

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.routes.auth import router as auth_router
from app.core.browser_security import BrowserSecurityMiddleware
from app.api.routes.documents import router as documents_router
from app.api.routes.workspaces import router as workspaces_router
from app.api.routes.workspace_members import router as workspace_members_router

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(workspaces_router)
app.include_router(workspace_members_router)
app.add_middleware(BrowserSecurityMiddleware)


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request, exc):
    # FastAPI's default validation response can echo plaintext password inputs.
    errors = [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
              for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})
