"""Deterministic qualification. Missing evidence is never a failed requirement."""

from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy import select

from backend.models import AssessmentCache, Correction, MappingReview, Requirement

ENGINE_VERSION = "qualification-v1"
FACTS = {
    "cmdb": ("Configuration management database (CMDB)", "boolean"),
    "implementation": ("Implementation services", "boolean"),
    "training": ("Staff and administrator training", "boolean"),
    "api": ("API integration", "boolean"),
    "sccm": ("Microsoft SCCM integration", "boolean"),
    "intune": ("Microsoft Intune integration", "boolean"),
    "problem_management": ("Problem management module", "boolean"),
    "us_staff": ("US-based delivery team", "boolean"),
    "ai_assistance": ("AI-assisted ticket solutions", "boolean"),
    "asset_capacity": ("Assets supported in a migration", "number"),
    "forms": ("Required proposal forms prepared", "boolean"),
    "acknowledgment": ("Addendum acknowledgment prepared", "boolean"),
}


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def validate_evidence(evidence: list, documents: dict) -> None:
    if not evidence:
        raise ValueError("Every requirement needs at least one source citation")
    for cite in evidence:
        doc = documents.get(cite["document_id"])
        if doc is None:
            raise ValueError("Citation references an unknown document")
        pages = doc.pages if hasattr(doc, "pages") else doc["pages"]
        page = next((p for p in pages if p["number"] == cite["page"]), None)
        quote = normalized(cite["quote"])
        if not page or len(quote) < 12 or quote not in normalized(page["text"]):
            raise ValueError(f"Citation is not grounded on page {cite['page']}")


def evaluate(body: dict, facts: dict) -> dict:
    if body.get("conflict"):
        return {
            "status": "review",
            "reason": "The source contains conflicting wording. Ask the buyer to clarify before relying on this requirement.",
        }
    if body["importance"] == "informational":
        return {
            "status": "info",
            "reason": "Context for preparing the proposal; no pass/fail test is applied.",
        }
    rule = body.get("rule")
    if not rule:
        return {
            "status": "unknown",
            "reason": "A person must verify this requirement. No reliable automatic comparison is available.",
        }
    fields = rule["fields"]
    values = [facts.get(field, {}).get("value") for field in fields]
    evidence = [facts.get(field, {}).get("evidence", "").strip() for field in fields]
    if any(value is None for value in values) or not all(evidence):
        return {
            "status": "unknown",
            "reason": "Company evidence is missing. Confirm the capability and record its supporting evidence.",
        }
    if rule["op"] == "all_true":
        matches = all(value is True for value in values)
    elif rule["op"] == "gte":
        matches = type(values[0]) in (int, float) and values[0] >= rule["value"]
    else:
        return {"status": "unknown", "reason": "This comparison requires manual verification."}
    if matches:
        return {
            "status": "met",
            "reason": "The recorded company evidence satisfies this comparison. Verify the evidence before submitting.",
        }
    if body["importance"] == "preferred":
        return {
            "status": "gap",
            "reason": "The company does not currently meet this preference. It is not treated as a mandatory blocker.",
        }
    return {
        "status": "blocker",
        "reason": "The recorded company capability does not satisfy a mandatory requirement. Resolve this gap before proceeding.",
    }


def snapshot(session, opportunity_id: str, stage: int, profile) -> dict:
    rows = session.scalars(
        select(Requirement)
        .where(Requirement.opportunity_id == opportunity_id, Requirement.sequence <= stage)
        .order_by(Requirement.sequence, Requirement.key)
    ).all()
    active = {}
    for row in rows:
        body = dict(row.body)
        mapping = session.scalars(
            select(MappingReview)
            .where(MappingReview.requirement_id == row.id)
            .order_by(MappingReview.created_at.desc(), MappingReview.id.desc())
        ).first()
        if mapping:
            body.update(mapping.body)
        key = body.get("supersedes_key") or row.key
        active[key] = (row, body)
    results, reused, evaluated = [], 0, 0
    for key, (row, body) in active.items():
        correction = session.scalars(
            select(Correction)
            .where(Correction.requirement_id == row.id)
            .order_by(Correction.created_at.desc(), Correction.id.desc())
        ).first()
        if correction:
            body["importance"] = correction.importance
        if body.get("action") == "removed":
            continue
        dependencies = body.get("rule", {}).get("fields", []) if body.get("rule") else []
        relevant = {key: profile.facts.get(key) for key in dependencies}
        fingerprint = hashlib.sha256(
            json.dumps(
                [ENGINE_VERSION, row.id, body, relevant, correction.id if correction else None],
                sort_keys=True,
            ).encode()
        ).hexdigest()
        cache = session.get(AssessmentCache, fingerprint)
        if cache:
            result = cache.result
            reused += 1
        else:
            result = evaluate(body, profile.facts)
            # Identical concurrent reads may populate the same cache entry.
            if session.bind.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert
            else:
                from sqlalchemy.dialects.sqlite import insert
            session.execute(
                insert(AssessmentCache)
                .values(id=fingerprint, result=result)
                .on_conflict_do_nothing(index_elements=["id"])
            )
            evaluated += 1
        results.append(
            {
                "id": row.id,
                "key": key,
                "sequence": row.sequence,
                **body,
                **result,
                "company_evidence": relevant,
                "correction": {
                    "id": correction.id,
                    "reason": correction.reason,
                    "importance": correction.importance,
                }
                if correction
                else None,
            }
        )
    counts = {
        s: sum(r["status"] == s for r in results)
        for s in ("met", "blocker", "unknown", "review", "gap", "info")
    }
    verdict = (
        "Resolve blockers"
        if counts["blocker"]
        else "Needs confirmation"
        if counts["unknown"] or counts["review"]
        else "No blockers in reviewed requirements"
    )
    return {
        "requirements": results,
        "counts": counts,
        "verdict": verdict,
        "stage": stage,
        "profile_version": profile.version,
        "cache": {"reused": reused, "evaluated": evaluated},
    }


def changes(before: dict, after: dict) -> list:
    old = {r["key"]: r for r in before["requirements"]}
    result = []
    for item in after["requirements"]:
        previous = old.get(item["key"])
        if previous and previous["id"] == item["id"]:
            continue
        result.append(
            {
                "key": item["key"],
                "type": item.get("action", "added"),
                "title": item["title"],
                "explanation": item.get("change_reason", "Newly documented requirement."),
                "before": previous,
                "after": item,
                "status_changed": previous is None or previous["status"] != item["status"],
            }
        )
    current = {r["key"] for r in after["requirements"]}
    for key, item in old.items():
        if key not in current:
            result.append(
                {
                    "key": key,
                    "type": "removed",
                    "title": item["title"],
                    "explanation": "This requirement was explicitly removed in a later version.",
                    "before": item,
                    "after": None,
                    "status_changed": True,
                }
            )
    return result
