from __future__ import annotations

import hmac
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, StrictBool, StrictFloat, StrictInt
from sqlalchemy import select, update

from backend.engine import FACTS, changes, snapshot
from backend.ingest import MAX_BYTES, validate_url
from backend.models import (
    DATA,
    Audit,
    Correction,
    Document,
    Job,
    MappingReview,
    Opportunity,
    Profile,
    Requirement,
    Session,
)
from backend.seed import seed


@asynccontextmanager
async def lifespan(app):
    seed()
    yield


app = FastAPI(title="BidLens", version="0.1.0", lifespan=lifespan)
origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def access(request: Request, call_next):
    if (
        request.method != "GET"
        and request.headers.get("origin")
        and request.headers["origin"] not in origins
    ):
        return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
    token = os.getenv("BIDLENS_API_TOKEN")
    if token and not hmac.compare_digest(
        request.headers.get("authorization", ""), "Bearer " + token
    ):
        return JSONResponse({"detail": "Authentication required"}, status_code=401)
    return await call_next(request)


def get_or_404(session, cls, id):
    row = session.get(cls, id)
    if row is None:
        raise HTTPException(404, "Not found")
    return row


def audit(session, action, detail):
    session.add(Audit(id=str(uuid.uuid4()), created_at=time.time(), action=action, detail=detail))


def ready():
    return bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL"))


def opportunity_dict(row):
    closed = datetime.fromisoformat(row.deadline) < datetime.now(UTC) if row.deadline else None
    return {
        "id": row.id,
        "title": row.title,
        "agency": row.agency,
        "source_url": row.source_url,
        "deadline": row.deadline,
        "closed": closed,
        "description": row.description,
        "mode": row.mode,
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "live_extraction": ready(),
        "pdf_engine": os.getenv("PDF_ENGINE", "pypdf"),
        "version": "0.1.0",
    }


@app.get("/api/opportunities")
def opportunities():
    with Session() as session:
        return [
            opportunity_dict(o)
            for o in session.scalars(select(Opportunity).order_by(Opportunity.id))
        ]


@app.get("/api/opportunities/{id}")
def opportunity(id: str, stage: int | None = None):
    with Session.begin() as session:
        row = get_or_404(session, Opportunity, id)
        docs = session.scalars(
            select(Document).where(Document.opportunity_id == id).order_by(Document.sequence)
        ).all()
        latest = max((d.sequence for d in docs), default=0)
        if stage is not None and stage not in {d.sequence for d in docs}:
            raise HTTPException(400, "Unknown document version")
        profile = get_or_404(session, Profile, "default")
        assessment = snapshot(session, id, latest if stage is None else stage, profile)
        before = snapshot(session, id, 0, profile)
        after = (
            assessment
            if stage is None or stage == latest
            else snapshot(session, id, latest, profile)
        )
        return {
            **opportunity_dict(row),
            "documents": [
                {
                    "id": d.id,
                    "name": d.name,
                    "sequence": d.sequence,
                    "pages": len(d.pages),
                    "url": d.url,
                    "sha256": d.sha256,
                    "mode": d.mode,
                    "pdf_available": Path(d.path).is_file(),
                }
                for d in docs
            ],
            "assessment": assessment,
            "changes": changes(before, after),
            "original_counts": before["counts"],
            "latest_stage": latest,
        }


@app.get("/api/documents/{id}/pages/{page}")
def evidence(id: str, page: int):
    with Session() as session:
        doc = get_or_404(session, Document, id)
        found = next((p for p in doc.pages if p["number"] == page), None)
        if not found:
            raise HTTPException(404, "Page not found")
        return {
            **found,
            "document_id": id,
            "name": doc.name,
            "url": doc.url,
            "pdf_available": Path(doc.path).is_file(),
        }


@app.get("/api/documents/{id}/pdf")
def pdf(id: str):
    with Session() as session:
        doc = get_or_404(session, Document, id)
        if not Path(doc.path).is_file():
            raise HTTPException(
                404,
                "PDF is not cached locally. Run the download script or open the original source.",
            )
        return FileResponse(
            doc.path,
            media_type="application/pdf",
            filename=f"{doc.id}.pdf",
            content_disposition_type="inline",
        )


@app.get("/api/profile")
def profile():
    with Session() as session:
        p = get_or_404(session, Profile, "default")
        return {
            "name": p.name,
            "version": p.version,
            "facts": p.facts,
            "fields": [{"key": k, "label": v[0], "type": v[1]} for k, v in FACTS.items()],
        }


class Fact(BaseModel):
    value: StrictBool | StrictInt | StrictFloat | None
    evidence: str = Field(max_length=2000)


class ProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    version: int
    facts: dict[str, Fact]


@app.put("/api/profile")
def update_profile(body: ProfileInput):
    for key, fact in body.facts.items():
        if key not in FACTS:
            raise HTTPException(422, f"Unknown capability: {key}")
        kind = FACTS[key][1]
        if fact.value is not None and (
            kind == "boolean"
            and type(fact.value) is not bool
            or kind == "number"
            and (type(fact.value) not in (int, float) or fact.value < 0)
        ):
            raise HTTPException(422, f"Invalid capability value: {key}")
    with Session.begin() as session:
        # Lock on PostgreSQL; version check also protects sequential stale saves on SQLite.
        p = session.scalar(select(Profile).where(Profile.id == "default").with_for_update())
        if p.version != body.version:
            raise HTTPException(409, "Profile changed in another window. Reload before saving.")
        old = p.facts
        new = {key: fact.model_dump() for key, fact in body.facts.items()}
        result = session.execute(
            update(Profile)
            .where(Profile.id == "default", Profile.version == body.version)
            .values(name=body.name.strip(), facts=new, version=body.version + 1)
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Profile changed in another window. Reload before saving.")
        audit(
            session,
            "profile_updated",
            {
                "version": body.version + 1,
                "changed_fields": [k for k in set(old) | set(new) if old.get(k) != new.get(k)],
            },
        )
    return profile()


class CorrectionInput(BaseModel):
    importance: Literal["mandatory", "preferred", "informational"]
    reason: str = Field(min_length=10, max_length=2000)


@app.post("/api/requirements/{id}/corrections")
def correct(id: str, body: CorrectionInput):
    if len(body.reason.strip()) < 10:
        raise HTTPException(422, "Explain your correction in at least 10 characters")
    with Session.begin() as session:
        get_or_404(session, Requirement, id)
        correction = Correction(
            id=str(uuid.uuid4()),
            requirement_id=id,
            created_at=time.time(),
            importance=body.importance,
            reason=body.reason.strip(),
        )
        session.add(correction)
        audit(
            session,
            "requirement_corrected",
            {
                "requirement_id": id,
                "importance": body.importance,
                "reason": body.reason,
                "scope": "This exact requirement version only",
            },
        )
    return {"ok": True, "id": correction.id}


@app.get("/api/audit")
def history():
    with Session() as session:
        return [
            {"id": a.id, "created_at": a.created_at, "action": a.action, "detail": a.detail}
            for a in session.scalars(select(Audit).order_by(Audit.created_at.desc()).limit(100))
        ]


class ImportInput(BaseModel):
    url: str = Field(max_length=2000)
    title: str = Field(min_length=3, max_length=200)
    agency: str = Field(min_length=2, max_length=200)
    opportunity_id: str | None = None


def queue(title, agency, url="", path="", opportunity_id=None):
    if not ready():
        raise HTTPException(
            503,
            "Live extraction needs OPENAI_API_KEY and OPENAI_MODEL in the server environment. The reviewed demo works without them.",
        )
    id, job_id = str(uuid.uuid4()), str(uuid.uuid4())
    with Session.begin() as session:
        sequence = 0
        if opportunity_id:
            existing = session.scalar(
                select(Opportunity).where(Opportunity.id == opportunity_id).with_for_update()
            )
            if not existing:
                raise HTTPException(404, "Opportunity not found")
            if existing.mode == "reviewed_demo":
                raise HTTPException(
                    409,
                    "Keep the reviewed demo intact. Import a new opportunity for live amendments.",
                )
            pending = session.scalar(
                select(Job).where(
                    Job.opportunity_id == opportunity_id,
                    Job.status.in_(["queued", "running", "failed"]),
                )
            )
            if pending:
                raise HTTPException(
                    409, "Finish or retry the existing document job before adding an amendment"
                )
            sequences = session.scalars(
                select(Document.sequence).where(Document.opportunity_id == opportunity_id)
            ).all()
            if not sequences:
                raise HTTPException(409, "Import the original RFP first")
            id, sequence = opportunity_id, max(sequences) + 1
        else:
            session.add(
                Opportunity(
                    id=id,
                    title=title.strip(),
                    agency=agency.strip(),
                    source_url=url,
                    mode="ai_unreviewed",
                    description="Live extraction. All findings require human verification; deadline and completeness have not been verified.",
                )
            )
        session.add(
            Job(
                id=job_id,
                opportunity_id=id,
                status="queued",
                payload={
                    "url": url,
                    "path": path,
                    "name": f"Addendum {sequence}" if sequence else "Original RFP",
                    "sequence": sequence,
                },
                updated_at=time.time(),
                attempts=0,
            )
        )
        audit(session, "import_queued", {"job_id": job_id, "opportunity_id": id})
    return {"job_id": job_id, "opportunity_id": id}


@app.post("/api/import/url", status_code=202)
def import_url(body: ImportInput):
    if not ready():
        raise HTTPException(
            503, "Configure OPENAI_API_KEY and OPENAI_MODEL to enable live extraction"
        )
    try:
        validate_url(body.url)
    except (ValueError, OSError) as exc:
        raise HTTPException(
            422, "Source must be an accessible HTTPS URL on an allowed government hostname"
        ) from exc
    return queue(body.title, body.agency, body.url, opportunity_id=body.opportunity_id)


@app.post("/api/import/upload", status_code=202)
async def upload(
    title: str = Form(min_length=3, max_length=200),
    agency: str = Form(min_length=2, max_length=200),
    file: UploadFile = File(),
    opportunity_id: str | None = Form(default=None),
):
    if not ready():
        raise HTTPException(
            503, "Configure OPENAI_API_KEY and OPENAI_MODEL to enable live extraction"
        )
    path = DATA / f"upload-{uuid.uuid4()}.pdf"
    try:
        size = 0
        with path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                if size == 0 and not chunk.startswith(b"%PDF-"):
                    raise HTTPException(422, "Upload must be a PDF")
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "Maximum PDF size is 20 MB")
                output.write(chunk)
        if size == 0:
            raise HTTPException(422, "PDF is empty")
        return queue(title, agency, path=str(path), opportunity_id=opportunity_id)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@app.get("/api/jobs")
def jobs():
    with Session() as session:
        return [
            {
                "id": j.id,
                "opportunity_id": j.opportunity_id,
                "status": j.status,
                "attempts": j.attempts,
                "updated_at": j.updated_at,
                "error": j.error,
            }
            for j in session.scalars(select(Job).order_by(Job.updated_at.desc()).limit(30))
        ]


@app.post("/api/jobs/{id}/retry")
def retry(id: str):
    with Session.begin() as session:
        j = get_or_404(session, Job, id)
        if j.status != "failed" or j.attempts >= 3:
            raise HTTPException(409, "Only failed jobs with fewer than 3 attempts can be retried")
        j.status, j.error, j.updated_at = "queued", None, time.time()
    return {"ok": True}


class MappingInput(BaseModel):
    field: str | None = None
    supersedes_key: str | None = None
    conflict: bool = False
    reason: str = Field(min_length=10, max_length=2000)


@app.get("/api/requirements/{id}/review-options")
def review_options(id: str):
    with Session.begin() as session:
        row = get_or_404(session, Requirement, id)
        if not row.body.get("review_required"):
            raise HTTPException(409, "Mapping applies to live extracted requirements")
        profile = get_or_404(session, Profile, "default")
        previous = (
            snapshot(session, row.opportunity_id, row.sequence - 1, profile)["requirements"]
            if row.sequence
            else []
        )
        return {
            "previous": [{"key": r["key"], "title": r["title"]} for r in previous],
            "fields": [{"key": k, "label": v[0]} for k, v in FACTS.items() if v[1] == "boolean"],
        }


@app.post("/api/requirements/{id}/mapping")
def map_requirement(id: str, body: MappingInput):
    if len(body.reason.strip()) < 10:
        raise HTTPException(422, "Explain the evidence for this mapping")
    if body.field and (body.field not in FACTS or FACTS[body.field][1] != "boolean"):
        raise HTTPException(422, "Choose a supported boolean capability or manual review")
    with Session.begin() as session:
        row = get_or_404(session, Requirement, id)
        if not row.body.get("review_required"):
            raise HTTPException(409, "Mapping applies to live extracted requirements")
        if body.supersedes_key:
            previous = snapshot(
                session,
                row.opportunity_id,
                row.sequence - 1,
                get_or_404(session, Profile, "default"),
            )["requirements"]
            if body.supersedes_key not in {r["key"] for r in previous}:
                raise HTTPException(
                    422, "A replacement must reference an earlier requirement in this opportunity"
                )
            peers = session.scalars(
                select(Requirement).where(
                    Requirement.opportunity_id == row.opportunity_id,
                    Requirement.sequence == row.sequence,
                    Requirement.id != row.id,
                )
            ).all()
            for peer in peers:
                mapping = session.scalar(
                    select(MappingReview)
                    .where(MappingReview.requirement_id == peer.id)
                    .order_by(MappingReview.created_at.desc())
                )
                if mapping and mapping.body.get("supersedes_key") == body.supersedes_key:
                    raise HTTPException(
                        409,
                        "Another finding in this document already replaces that requirement; review the conflict instead",
                    )
        reviewed = {
            "supersedes_key": body.supersedes_key,
            "rule": {"op": "all_true", "fields": [body.field]} if body.field else None,
            "conflict": body.conflict,
            "action": "conflict"
            if body.conflict
            else "replaced"
            if body.supersedes_key
            else "added",
            "change_reason": body.reason.strip(),
            "review_required": False,
            "mapping_reviewed": True,
        }
        session.add(
            MappingReview(
                id=str(uuid.uuid4()), requirement_id=id, created_at=time.time(), body=reviewed
            )
        )
        audit(
            session,
            "mapping_reviewed",
            {
                "requirement_id": id,
                "field": body.field,
                "supersedes_key": body.supersedes_key,
                "conflict": body.conflict,
                "reason": body.reason.strip(),
            },
        )
    return {"ok": True}


@app.post("/api/jobs/{id}/dismiss")
def dismiss_job(id: str):
    with Session.begin() as session:
        job = get_or_404(session, Job, id)
        if job.status != "failed":
            raise HTTPException(409, "Only failed imports can be dismissed")
        job.status, job.updated_at = "dismissed", time.time()
        audit(
            session, "failed_import_dismissed", {"job_id": id, "opportunity_id": job.opportunity_id}
        )
    return {"ok": True}
