"""Schemas for the orchestrate-parse endpoint."""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel


class OrchestrationStepResult(BaseModel):
    document_id: uuid.UUID
    file_name: str
    declared_type: str
    resolved_type: str
    reclassified: bool
    run_classifier: bool
    status: str  # "complete" | "failed"
    error: Optional[str] = None


class OrchestrationResult(BaseModel):
    period_id: uuid.UUID
    parsed: int
    failed: int
    classifier_ran: bool
    classifier_updated: int
    steps: list[OrchestrationStepResult]
