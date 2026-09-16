"""
DevLens AI — Job Status Router
Polling endpoint for indexing pipeline progress (FR-2.6).
"""
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.dependencies import CurrentUserId
from app.database import get_db_context
from app.models import IndexingJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobStatusOut(BaseModel):
    job_id: uuid.UUID
    repository_id: uuid.UUID
    stage: str
    progress_pct: int
    error_message: Optional[str]

    model_config = {"from_attributes": True}


@router.get("/{job_id}", response_model=JobStatusOut)
async def get_job_status(job_id: uuid.UUID, user_id: CurrentUserId):
    """
    Poll for pipeline progress (FR-2.6).
    Returns current stage, progress percentage, and any error message.
    """
    async with get_db_context() as db:
        result = await db.execute(select(IndexingJob).where(IndexingJob.id == job_id))
        job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusOut.model_validate(job)
