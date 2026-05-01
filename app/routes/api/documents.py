import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_mortgage_extractor, get_paystub_extractor, get_statement_extractor
from app.models.document import Document
from app.schemas.api_responses import SourceAccountRequest
from app.schemas.document import DocumentRead
from app.services import document as document_service
from app.services import parse as parse_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


@router.post("/periods/{period_id}/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    period_id: uuid.UUID,
    document_type: str = Form(...),
    source_account_code: int | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
) -> DocumentRead:
    try:
        doc = await document_service.save_upload(
            db,
            period_id=period_id,
            document_type=document_type,
            source_account_code=source_account_code,
            upload=file,
        )
    except document_service.DocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DocumentRead.model_validate(doc)


@router.delete("/periods/{period_id}/documents/{document_id}")
async def delete_document(
    period_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        await document_service.delete_document(db, document_id)
    except document_service.DocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/periods/{period_id}/documents/{document_id}/parse", response_model=DocumentRead)
async def parse_document(
    period_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    statement_agent: Agent = Depends(get_statement_extractor),
    paystub_agent: Agent = Depends(get_paystub_extractor),
    mortgage_agent: Agent = Depends(get_mortgage_extractor),
) -> DocumentRead:
    doc = await db.get(Document, document_id)
    if doc is None or doc.period_id != period_id:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        updated = await parse_service.parse_document(
            db,
            document=doc,
            statement_agent=statement_agent,
            paystub_agent=paystub_agent,
            mortgage_agent=mortgage_agent,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return DocumentRead.model_validate(updated)


@router.post("/periods/{period_id}/documents/{document_id}/unpost")
async def unpost_document(
    period_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    from sqlalchemy import delete
    from app.models.raw_transaction import RawTransaction

    result = await db.execute(
        delete(RawTransaction).where(
            RawTransaction.document_id == document_id,
            RawTransaction.status.in_(["staged", "approved"]),
        ).returning(RawTransaction.raw_txn_id)
    )
    unposted = len(result.all())
    await db.commit()
    return {"unposted": unposted}


@router.patch("/periods/{period_id}/documents/{document_id}/source-account", response_model=DocumentRead)
async def set_source_account(
    period_id: uuid.UUID,
    document_id: uuid.UUID,
    body: SourceAccountRequest,
    db: AsyncSession = Depends(get_db_session),
) -> DocumentRead:
    doc = await db.get(Document, document_id)
    if doc is None or doc.period_id != period_id:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        updated = await document_service.update_source_account(db, document_id, body.source_account_code)
    except document_service.DocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DocumentRead.model_validate(updated)
