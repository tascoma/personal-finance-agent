"""Orchestration service — plan-then-execute parse for a batch of documents.

The flow:
  1. Load every `parse_status="pending"` document for the period.
  2. Build a short digest per document (filename, declared type, extension,
     small content peek) — never the full file.
  3. Call `run_orchestrator` once to get an `OrchestrationPlan` covering the batch.
  4. For each step in the plan, persist any `document_type` correction, then call
     the existing `parse_service.parse_document` extractor.
  5. If any step requested it, run `classify_service.classify_period` once for
     the period at the end.

Per-step failures are caught so a single bad file doesn't abort the rest.
"""

import logging
import uuid
from pathlib import Path
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import DocumentDigest, OrchestrationPlan, run_orchestrator
from app.models.document import Document
from app.schemas.orchestrate import OrchestrationResult, OrchestrationStepResult
from app.services import classify as classify_service
from app.services import parse as parse_service
from app.services.file_readers import (
    ParseError,
    extract_csv_rows,
    extract_pdf_text,
    extract_xlsx_rows,
)

logger = logging.getLogger(__name__)

PDF_PEEK_CHARS = 800
TABULAR_PEEK_ROWS = 10


def _build_digest(document: Document) -> DocumentDigest:
    """Read a small content peek from disk for the orchestrator's routing decision."""
    path = Path(document.file_path)
    extension = path.suffix.lower()
    peek = ""
    try:
        if extension == ".pdf":
            text = extract_pdf_text(path)
            peek = text[:PDF_PEEK_CHARS]
        elif extension == ".csv":
            rows = extract_csv_rows(path)
            peek = "\n".join(", ".join(f"{k}={v}" for k, v in r.items()) for r in rows[:TABULAR_PEEK_ROWS])
        elif extension == ".xlsx":
            rows_x = extract_xlsx_rows(path)
            peek = "\n".join(" | ".join(str(c) if c is not None else "" for c in r) for r in rows_x[:TABULAR_PEEK_ROWS])
        else:
            peek = f"(unsupported extension: {extension})"
    except ParseError as exc:
        peek = f"(could not read file: {exc})"
    except Exception as exc:
        logger.warning("Unexpected error reading peek for %s: %s", path, exc)
        peek = f"(error reading file: {exc})"

    return DocumentDigest(
        document_id=document.document_id,
        file_name=document.file_name,
        declared_type=document.document_type,
        file_extension=extension,
        content_peek=peek,
    )


async def orchestrate_parse(
    db: AsyncSession,
    period_id: uuid.UUID,
) -> OrchestrationResult:
    docs_result = await db.scalars(
        select(Document).where(
            Document.period_id == period_id,
            Document.parse_status == "pending",
        )
    )
    pending: Sequence[Document] = docs_result.all()
    if not pending:
        return OrchestrationResult(
            period_id=period_id,
            parsed=0,
            failed=0,
            classifier_ran=False,
            classifier_updated=0,
            steps=[],
        )

    docs_by_id: dict[uuid.UUID, Document] = {d.document_id: d for d in pending}
    digests = [_build_digest(d) for d in pending]

    plan: OrchestrationPlan = await run_orchestrator(digests)
    logger.info(
        "Orchestrator planned %d steps for period %s (from %d pending docs)",
        len(plan.steps),
        period_id,
        len(pending),
    )

    step_results: list[OrchestrationStepResult] = []
    any_classifier_requested = False
    parsed = 0
    failed = 0

    planned_ids = {step.document_id for step in plan.steps}
    missing = [d for d in pending if d.document_id not in planned_ids]
    for d in missing:
        logger.warning("Orchestrator skipped document %s — recording as failed", d.document_id)
        step_results.append(
            OrchestrationStepResult(
                document_id=d.document_id,
                file_name=d.file_name,
                declared_type=d.document_type,
                resolved_type=d.document_type,
                reclassified=False,
                run_classifier=False,
                status="failed",
                error="Orchestrator did not return a plan for this document",
            )
        )
        failed += 1

    for step in plan.steps:
        doc = docs_by_id.get(step.document_id)
        if doc is None:
            logger.warning(
                "Orchestrator returned unknown document_id %s — skipping", step.document_id
            )
            continue

        declared = doc.document_type
        reclassified = step.resolved_type != declared
        if reclassified:
            logger.info(
                "Orchestrator reclassified document %s: %s → %s (reason: %s)",
                doc.document_id,
                declared,
                step.resolved_type,
                step.reason,
            )
            doc.document_type = step.resolved_type
            await db.commit()

        if step.run_classifier:
            any_classifier_requested = True

        try:
            await parse_service.parse_document(db, doc.document_id)
            parsed += 1
            step_results.append(
                OrchestrationStepResult(
                    document_id=doc.document_id,
                    file_name=doc.file_name,
                    declared_type=declared,
                    resolved_type=step.resolved_type,
                    reclassified=reclassified,
                    run_classifier=step.run_classifier,
                    status="complete",
                )
            )
        except ParseError as exc:
            failed += 1
            step_results.append(
                OrchestrationStepResult(
                    document_id=doc.document_id,
                    file_name=doc.file_name,
                    declared_type=declared,
                    resolved_type=step.resolved_type,
                    reclassified=reclassified,
                    run_classifier=step.run_classifier,
                    status="failed",
                    error=str(exc),
                )
            )

    classifier_updated = 0
    if any_classifier_requested and parsed > 0:
        try:
            classifier_updated = await classify_service.classify_period(db, period_id)
            logger.info(
                "Classifier updated %d transactions for period %s after orchestration",
                classifier_updated,
                period_id,
            )
        except Exception:
            logger.exception(
                "Classifier failed after orchestration for period %s — continuing", period_id
            )

    return OrchestrationResult(
        period_id=period_id,
        parsed=parsed,
        failed=failed,
        classifier_ran=any_classifier_requested and parsed > 0,
        classifier_updated=classifier_updated,
        steps=step_results,
    )
