from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.config import settings
from app.db import get_db
from app.models.document import Document
from app.models.record import AuctionRecord
from app.schemas.common import Page
from app.schemas.document import DocumentRead, DocumentStatus, DocumentUploadResponse
from app.services.files import create_thumbnail, sha256_bytes
from app.services.queue import enqueue_preprocess
from app.services.storage import generate_key, storage_client

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    data = await file.read()
    await file.close()
    max_bytes = settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large",
        )

    file_hash = sha256_bytes(data)
    existing = await db.execute(select(Document).where(Document.hash_sha256 == file_hash))
    existing_doc = existing.scalar_one_or_none()
    if existing_doc:
        return DocumentUploadResponse(status="duplicate", existing_id=existing_doc.id)

    original_key = generate_key("originals", file.filename)
    storage_client.upload_bytes(original_key, data, file.content_type)

    thumb_key = None
    try:
        thumb_bytes = create_thumbnail(data)
        thumb_key = generate_key("thumbs", "thumb.jpg")
        storage_client.upload_bytes(thumb_key, thumb_bytes, "image/jpeg")
    except Exception:
        thumb_key = None

    doc = Document(
        source="upload",
        uploaded_by=current_user.id,
        status="queued",
        original_path=original_key,
        thumb_path=thumb_key,
        hash_sha256=file_hash,
    )
    db.add(doc)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.execute(select(Document).where(Document.hash_sha256 == file_hash))
        existing_doc = existing.scalar_one_or_none()
        if existing_doc:
            return DocumentUploadResponse(status="duplicate", existing_id=existing_doc.id)
        raise

    await db.refresh(doc)
    enqueue_preprocess(str(doc.id))
    return DocumentUploadResponse(status="queued", document_id=doc.id)


@router.get("", response_model=Page[DocumentRead])
async def list_documents(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    offset = (page - 1) * per_page
    result = await db.execute(select(Document).order_by(Document.created_at.desc()).offset(offset).limit(per_page))
    items = result.scalars().all()
    total = await db.scalar(select(func.count()).select_from(Document))
    return Page(items=items, page=page, per_page=per_page, total=total or 0)


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{document_id}/status", response_model=DocumentStatus)
async def get_document_status(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    record = await db.execute(
        select(AuctionRecord.needs_review).where(AuctionRecord.document_id == doc.id)
    )
    needs_review = record.scalar_one_or_none()
    return DocumentStatus(
        id=doc.id,
        status=doc.status,
        error_message=doc.error_message,
        needs_review=needs_review,
    )


@router.post("/{document_id}/reprocess", response_model=DocumentStatus)
async def reprocess_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.status = "queued"
    doc.error_message = None
    doc.processing_started_at = None
    doc.processing_completed_at = None
    await db.commit()
    enqueue_preprocess(str(doc.id))
    return DocumentStatus(id=doc.id, status=doc.status)
