import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, Confab, ConfabLearning
from schemas import LearningCreate, LearningUpdate, LearningResponse
from deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["learnings"])


@router.get("/confabs/{confab_id}/learnings", response_model=List[LearningResponse])
async def list_learnings(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    learnings = db.query(ConfabLearning).filter(ConfabLearning.confab_id == confab_id).order_by(ConfabLearning.created_at.desc()).all()
    return [LearningResponse.model_validate(l) for l in learnings]


@router.post("/confabs/{confab_id}/learnings", response_model=LearningResponse)
async def create_learning(
    confab_id: int,
    learning: LearningCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    db_learning = ConfabLearning(
        confab_id=confab_id,
        content=learning.content,
        summary=learning.summary,
        tags=learning.tags,
        source=learning.source,
        source_thread_id=learning.source_thread_id,
        author_type="user",
        author_id=current_user.id,
        status="draft",
    )
    db.add(db_learning)
    db.commit()
    db.refresh(db_learning)
    return LearningResponse.model_validate(db_learning)


@router.put("/confabs/{confab_id}/learnings/{learning_id}", response_model=LearningResponse)
async def update_learning(
    confab_id: int,
    learning_id: int,
    update: LearningUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    learning = db.query(ConfabLearning).filter(ConfabLearning.id == learning_id, ConfabLearning.confab_id == confab_id).first()
    if not learning:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning not found")

    if update.content is not None:
        learning.content = update.content
    if update.summary is not None:
        learning.summary = update.summary
    if update.tags is not None:
        learning.tags = update.tags
    if update.status is not None:
        learning.status = update.status

    db.commit()
    db.refresh(learning)
    return LearningResponse.model_validate(learning)


@router.delete("/confabs/{confab_id}/learnings/{learning_id}")
async def delete_learning(
    confab_id: int,
    learning_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    learning = db.query(ConfabLearning).filter(ConfabLearning.id == learning_id, ConfabLearning.confab_id == confab_id).first()
    if not learning:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning not found")

    db.delete(learning)
    db.commit()
    return {"message": "Learning deleted"}
