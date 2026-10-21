"""Rebuild selected, curated annotations; never substitute synthetic RFP text."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data/sources"
docs = []
for stem, seq, url, name in [
    (
        "26-38-original",
        0,
        "https://www.a2gov.org/media/b2gno2i0/rfp_26-38_document.pdf",
        "Original RFP",
    ),
    (
        "26-38-addendum-1",
        1,
        "https://www.a2gov.org/media/mv0jeano/rfp_26-38_addendum1.pdf",
        "Addendum 1",
    ),
]:
    docs.append(
        dict(
            id=stem,
            sequence=seq,
            name=name,
            url=url,
            sha256=hashlib.sha256((SOURCES / (stem + ".pdf")).read_bytes()).hexdigest(),
            pages=json.loads((SOURCES / (stem + ".json")).read_text()),
        )
    )


def cite(doc, page, start, end=None):
    text = re.sub(r"\s+", " ", docs[doc]["pages"][page - 1]["text"]).strip()
    i = text.index(start)
    j = text.index(end, i) + len(end) if end else i + len(start)
    return dict(document_id=docs[doc]["id"], page=page, quote=text[i:j])


requirements = []


def add(key, title, seq, evidence, fields=None, importance="mandatory", **kw):
    body = dict(
        title=title,
        importance=importance,
        category=kw.pop("category", "Capability"),
        evidence=evidence,
        action="added" if seq else "original",
        rule=dict(op="all_true", fields=fields) if fields else None,
        **kw,
    )
    requirements.append(dict(id=f"{key}-v{seq}", key=key, sequence=seq, body=body))


add(
    "cmdb",
    "Configuration management database",
    0,
    [cite(0, 11, "The system must include a configuration management database (CMDB).")],
    ["cmdb"],
)
add(
    "implementation",
    "Implementation services",
    0,
    [cite(0, 12, "The vendor must provide implementation services", "and deployment.")],
    ["implementation"],
)
add(
    "training",
    "Training for IT staff",
    0,
    [cite(0, 12, "The vendor must provide training for IT staff and system administrators.")],
    ["training"],
)
add(
    "api",
    "Integration API",
    0,
    [cite(0, 11, "The system must support API integration capabilities", "systems.")],
    ["api"],
)
add(
    "microsoft",
    "SCCM and Intune integration",
    0,
    [
        cite(
            0,
            11,
            "The system must support integration with the City’s SCCM",
            "update asset information in the CMDB.",
        )
    ],
    ["sccm", "intune"],
)
add(
    "migration",
    "Migration scope",
    0,
    [cite(0, 3, "The project will include vendor selection", "training.")],
    category="Delivery",
    note="Migration is required, but its volume and scope are not specified here.",
)
add(
    "forms",
    "Required proposal forms",
    0,
    [cite(0, 5, "A proposal may be disqualified", "Document")],
    ["forms"],
    category="Submission",
)
add(
    "ai",
    "AI-assisted ticket solutions",
    0,
    [
        cite(
            0,
            12,
            "The system should provide AI-assisted capabilities",
            "incidents or service requests.",
        )
    ],
    ["ai_assistance"],
    importance="preferred",
)
add(
    "microsoft",
    "Microsoft integration wording conflicts",
    1,
    [
        cite(
            1,
            2,
            "Answer 5: The City has identified integration",
            "primary integrations anticipated for the initial implementation.",
        ),
        cite(
            1,
            3,
            "Answer 9: The following integrations",
            "Microsoft Intune – Asset inventory and CMDB population.",
        ),
    ],
    ["sccm", "intune"],
    conflict=True,
    change_reason="Answer 5 describes SCCM or Intune. Answer 9 lists both as required at initial implementation. Neither answer explicitly overrides the other; retain the conflict for buyer clarification.",
)
add(
    "migration",
    "Migrate approximately 2,380 assets",
    1,
    [cite(1, 3, "Answer 11: The City does not anticipate", "approximately 2,380 assets.")],
    category="Delivery",
    change_reason="The amendment narrows the expected migration: current assets, without historical tickets or knowledge articles. Approximately 2,380 assets is a planning quantity, not a certification threshold.",
    note="Check migration approach, mapping, validation, and capacity with the delivery team.",
)
add(
    "problem",
    "Problem management in scope",
    1,
    [cite(1, 3, "Answer 12: The City expects", "overall implementation scope and pricing.")],
    ["problem_management"],
    change_reason="Answer 12 explicitly includes Problem Management in overall scope and pricing. It was not separately listed in the original functional modules. A phased rollout is allowed.",
)
add(
    "us_staff",
    "US-based resources preferred",
    1,
    [
        cite(
            1,
            6,
            "Question 26: Are there any restrictions",
            "Answer 26: It is preferred that the resources are located in the US but not required.",
        )
    ],
    ["us_staff"],
    importance="preferred",
    category="Delivery",
    change_reason="US resources are preferred, not mandatory. An offshore team is a preference gap, not a disqualification.",
)
add(
    "acknowledgment",
    "Acknowledge Addendum 1",
    1,
    [cite(1, 1, "The Proposer is to acknowledge receipt", "considered non-conforming.")],
    ["acknowledgment"],
    category="Submission",
    change_reason="The proposal must acknowledge this addendum and its attachments. This is a separate submission task.",
)
add(
    "budget",
    "Budget remains unspecified",
    1,
    [
        cite(
            1,
            8,
            "Question 45: What is the estimated budget",
            "Answer 45: A project budget has not yet been established.",
        )
    ],
    importance="informational",
    category="Commercial",
    change_reason="The buyer explicitly says a budget has not been established. BidLens does not invent an estimate.",
)
for r in requirements:
    if r["key"] in ["microsoft", "migration"] and r["sequence"] == 1:
        r["body"]["action"] = "conflict" if r["key"] == "microsoft" else "clarified"

facts = {}
for key in ["cmdb", "implementation", "training", "api", "sccm", "intune"]:
    facts[key] = {
        "value": True,
        "evidence": "Fictional demo: confirmed in Northstar Civic product and delivery capability sheet.",
    }
for key in ["problem_management", "us_staff", "ai_assistance"]:
    facts[key] = {
        "value": False,
        "evidence": "Fictional demo: capability not offered in the current company profile.",
    }
for key in ["forms", "acknowledgment"]:
    facts[key] = {"value": None, "evidence": ""}
facts["asset_capacity"] = {
    "value": 3000,
    "evidence": "Fictional demo: migration dry run covering 3,000 asset records.",
}
fixture = {
    "opportunity": {
        "id": "a2-26-38",
        "title": "IT Service Management System Replacement",
        "agency": "City of Ann Arbor, Michigan",
        "source_url": "https://www.a2gov.org/finance-and-administrative-services/purchasing/request-for-proposals/",
        "deadline": "2026-07-29T14:00:00-04:00",
        "description": "Replace the city’s IT service management platform, migrate current assets, and deliver implementation and staff training.",
        "mode": "reviewed_demo",
    },
    "documents": docs,
    "requirements": requirements,
    "profile": {
        "id": "default",
        "name": "Northstar Civic · example company",
        "version": 1,
        "facts": facts,
    },
}
(ROOT / "data/demo.json").write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n")
print(
    f"Built {len(requirements)} evidence-backed requirement versions across {sum(len(d['pages']) for d in docs)} source pages"
)
