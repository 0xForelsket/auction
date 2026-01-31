from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.whatsapp import WhatsappMeta

router = APIRouter()


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.json()
    message_id = payload.get("message_id") or payload.get("id")
    from_number = payload.get("from") or payload.get("from_number")
    if not message_id or not from_number:
        raise HTTPException(status_code=400, detail="Missing message_id or from_number")

    existing = await db.execute(select(WhatsappMeta).where(WhatsappMeta.message_id == message_id))
    if existing.scalar_one_or_none():
        return {"status": "duplicate"}

    meta = WhatsappMeta(
        message_id=message_id,
        from_number=from_number,
        chat_id=payload.get("chat_id"),
        received_at=datetime.now(timezone.utc),
        status="received",
        raw_payload=payload,
    )
    db.add(meta)
    await db.commit()
    return {"status": "received"}
