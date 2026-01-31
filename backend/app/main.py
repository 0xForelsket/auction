from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, documents, exports, records, review, webhooks
from app.config import settings
from app.services.storage import storage_client


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
app.include_router(documents.router, prefix="/v1/documents", tags=["documents"])
app.include_router(records.router, prefix="/v1/records", tags=["records"])
app.include_router(review.router, prefix="/v1/review", tags=["review"])
app.include_router(exports.router, prefix="/v1/exports", tags=["exports"])
app.include_router(webhooks.router, prefix="/v1/webhooks", tags=["webhooks"])


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.on_event("startup")
def ensure_storage_bucket() -> None:
    storage_client.ensure_bucket()
