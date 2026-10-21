"""Durable job worker. Run separately with python -m backend.worker."""

import hashlib
import time
import uuid
from pathlib import Path

from sqlalchemy import select, update

from backend.ingest import download, extract, parse_pdf
from backend.models import DATA, Audit, Document, Job, Requirement, Session
from backend.seed import seed


def claim():
    now = time.time()
    with Session.begin() as session:
        # A crashed process can be retried after a 30-minute lease. Model calls are bounded.
        session.execute(
            update(Job)
            .where(Job.status == "running", Job.updated_at < now - 1800)
            .values(status="queued", error="Worker lease expired; retrying")
        )
        candidates = session.scalars(
            select(Job).where(Job.status == "queued").order_by(Job.updated_at)
        ).all()
        for job in candidates:
            if job.attempts >= 3:
                job.status, job.error = "failed", "Retry limit reached"
                continue
            result = session.execute(
                update(Job)
                .where(Job.id == job.id, Job.status == "queued")
                .values(status="running", attempts=job.attempts + 1, updated_at=now)
            )
            if result.rowcount == 1:
                return job.id
    return None


def process(job_id):
    with Session() as session:
        job = session.get(Job, job_id)
        payload, opportunity_id = job.payload, job.opportunity_id
    path = Path(payload.get("path") or DATA / f"{job_id}.pdf")
    try:
        if not path.exists():
            download(payload["url"], path)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        with Session() as session:
            duplicate = session.scalar(
                select(Document.id).where(
                    Document.opportunity_id == opportunity_id, Document.sha256 == sha
                )
            )
        if duplicate:
            raise ValueError("This exact PDF is already in this opportunity")
        pages = parse_pdf(path)
        doc_id = f"doc-{job_id}"

        def heartbeat():
            with Session.begin() as session:
                session.execute(
                    update(Job)
                    .where(Job.id == job_id, Job.status == "running")
                    .values(updated_at=time.time())
                )

        requirements = extract(pages, doc_id, heartbeat=heartbeat)
        with Session.begin() as session:
            # Imported amendments remain separate findings until a reviewer maps precedence.
            session.add(
                Document(
                    id=doc_id,
                    opportunity_id=opportunity_id,
                    sequence=payload.get("sequence", 0),
                    name=payload["name"],
                    url=payload.get("url", ""),
                    sha256=sha,
                    path=str(path),
                    pages=pages,
                    mode="ai_unreviewed",
                )
            )
            for i, body in enumerate(requirements):
                session.add(
                    Requirement(
                        id=f"{doc_id}-{i}",
                        key=f"{doc_id}-{i}",
                        sequence=payload.get("sequence", 0),
                        opportunity_id=opportunity_id,
                        body=body,
                    )
                )
            job = session.get(Job, job_id)
            job.status, job.error, job.updated_at = "completed", None, time.time()
            session.add(
                Audit(
                    id=str(uuid.uuid4()),
                    created_at=time.time(),
                    action="document_extracted",
                    detail={
                        "job_id": job_id,
                        "document_id": doc_id,
                        "sha256": sha,
                        "requirements": len(requirements),
                    },
                )
            )
    except Exception as exc:
        with Session.begin() as session:
            job = session.get(Job, job_id)
            # No raw provider messages: they may contain request data or credentials.
            job.error = (
                str(exc)[:350]
                if isinstance(exc, ValueError)
                else f"{type(exc).__name__}: extraction failed. Check server configuration or retry."
            )
            job.status, job.updated_at = "failed", time.time()


def main():
    seed()
    print("BidLens worker ready", flush=True)
    while True:
        job_id = claim()
        if job_id:
            process(job_id)
        else:
            time.sleep(2)


if __name__ == "__main__":
    main()
