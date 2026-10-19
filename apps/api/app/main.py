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
