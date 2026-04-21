import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, Confab
from deps import get_current_user
from document_store_v2 import DocumentServiceV2, get_accepted_formats
from document_store_v2.schemas import (
    DocumentUploadRequest as DocumentUploadRequestV2,
    DocumentVersionRequest,
    DocumentResponse as DocumentResponseV2,
    DocumentContentResponse,
    DocumentListResponse,
    VersionListResponse,
    DocumentUploadResponse as DocumentUploadResponseV2,
    DocumentStageHint,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["documents"])


@router.post("/confabs/{confab_id}/documents", response_model=DocumentUploadResponseV2)
async def upload_document_v2(
    confab_id: int,
    body: DocumentUploadRequestV2,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a new document (V2 - versioned)."""
    # Verify confab ownership
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    service = DocumentServiceV2(db)
    try:
        result = await service.upload_document(
            confab_id=confab_id,
            content_base64=body.content_base64,
            filename=body.filename,
            declared_content_type=body.content_type,
            metadata=body.metadata,
            user_id=current_user.id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/confabs/{confab_id}/documents", response_model=DocumentListResponse)
async def list_documents_v2(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all documents for a confab (V2 - versioned)."""
    # Verify confab ownership
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    service = DocumentServiceV2(db)
    return await service.list_documents(confab_id)


@router.get("/confabs/{confab_id}/documents/{document_id}", response_model=DocumentResponseV2)
async def get_document_v2(
    confab_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get document metadata (V2 - versioned)."""
    # Verify confab ownership
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    service = DocumentServiceV2(db)
    try:
        return await service.get_document(document_id, confab_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/confabs/{confab_id}/documents/{document_id}")
async def archive_document_v2(
    confab_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Archive (soft delete) a document (V2 - versioned)."""
    # Verify confab ownership
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    service = DocumentServiceV2(db)
    try:
        await service.archive_document(document_id, confab_id)
        return {"message": "Document archived"}
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/confabs/{confab_id}/documents/{document_id}/versions", response_model=VersionListResponse)
async def list_document_versions(
    confab_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all versions of a document."""
    # Verify confab ownership
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    service = DocumentServiceV2(db)
    try:
        return await service.list_versions(document_id, confab_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/confabs/{confab_id}/documents/{document_id}/versions/latest", response_model=DocumentContentResponse)
async def get_latest_document_version(
    confab_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get content for the latest document version."""
    # Verify confab ownership
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    service = DocumentServiceV2(db)
    try:
        return await service.get_latest_version_content(document_id, confab_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/confabs/{confab_id}/documents/{document_id}/versions/{version_number}", response_model=DocumentContentResponse)
async def get_document_version_content(
    confab_id: int,
    document_id: int,
    version_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get content for a specific document version."""
    # Verify confab ownership
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    service = DocumentServiceV2(db)
    try:
        return await service.get_version_content(document_id, version_number, confab_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/confabs/{confab_id}/documents/{document_id}/versions", response_model=VersionListResponse)
async def create_document_version(
    confab_id: int,
    document_id: int,
    body: DocumentVersionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new version of an existing document."""
    # Verify confab ownership
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    service = DocumentServiceV2(db)
    try:
        await service.create_version(
            document_id=document_id,
            content_base64=body.content_base64,
            metadata=body.metadata,
            user_id=current_user.id,
        )
        # Return updated version list
        return await service.list_versions(document_id, confab_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/documents/accepted-formats", response_model=DocumentStageHint)
async def get_accepted_document_formats():
    """Get accepted document formats and upload hints (for Foreman UI)."""
    return DocumentStageHint(
        accepted_formats=get_accepted_formats(),
    )
