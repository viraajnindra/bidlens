import json

import pytest

from backend.engine import evaluate, validate_evidence
from backend.models import ROOT


def test_entire_reviewed_fixture_is_citation_grounded():
    fixture = json.loads((ROOT / "data/demo.json").read_text())
    docs = {d["id"]: d for d in fixture["documents"]}
    for req in fixture["requirements"]:
        validate_evidence(req["body"]["evidence"], docs)
    assert sum(len(d["pages"]) for d in docs.values()) == 85
    assert len(fixture["requirements"]) == 14


@pytest.mark.parametrize(
    "value,evidence,importance,expected",
    [
        (True, "Product documentation", "mandatory", "met"),
        (False, "Not offered", "mandatory", "blocker"),
        (None, "", "mandatory", "unknown"),
        (True, "", "mandatory", "unknown"),
        (False, "Offshore team", "preferred", "gap"),
        (False, "", "preferred", "unknown"),
        (False, "Not offered", "informational", "info"),
    ],
)
def test_missing_is_not_failed_and_preferred_is_not_mandatory(
    value, evidence, importance, expected
):
    body = {"importance": importance, "rule": {"op": "all_true", "fields": ["capability"]}}
    assert (
        evaluate(body, {"capability": {"value": value, "evidence": evidence}})["status"] == expected
    )


def test_conflict_cannot_be_silenced_by_profile_or_classification():
    assert evaluate({"importance": "informational", "conflict": True}, {})["status"] == "review"


def test_numeric_comparison_does_not_accept_boolean_as_number():
    body = {"importance": "mandatory", "rule": {"op": "gte", "fields": ["assets"], "value": 1}}
    assert evaluate(body, {"assets": {"value": True, "evidence": "x"}})["status"] == "blocker"
    assert (
        evaluate(body, {"assets": {"value": 3000, "evidence": "capacity test"}})["status"] == "met"
    )


def test_unknown_comparison_and_manual_rule_stay_unknown():
    assert evaluate({"importance": "mandatory"}, {})["status"] == "unknown"
    assert (
        evaluate({"importance": "mandatory", "rule": {"op": "unsupported", "fields": []}}, {})[
            "status"
        ]
        == "unknown"
    )


@pytest.mark.parametrize(
    "bad",
    [
        [
            {
                "document_id": "missing",
                "page": 1,
                "quote": "The system must support access controls.",
            }
        ],
        [{"document_id": "doc", "page": 2, "quote": "The system must support access controls."}],
        [{"document_id": "doc", "page": 1, "quote": "Invented citation that does not exist."}],
        [],
    ],
)
def test_rejects_hallucinated_or_missing_citations(bad):
    with pytest.raises(ValueError):
        validate_evidence(
            bad,
            {"doc": {"pages": [{"number": 1, "text": "The system must support access controls."}]}},
        )


def test_original_and_amendment_have_expected_consequences(client):
    before = client.get("/api/opportunities/a2-26-38?stage=0").json()
    after = client.get("/api/opportunities/a2-26-38").json()
    assert before["assessment"]["counts"] == {
        "met": 5,
        "blocker": 0,
        "unknown": 2,
        "review": 0,
        "gap": 1,
        "info": 0,
    }
    assert after["assessment"]["counts"] == {
        "met": 4,
        "blocker": 1,
        "unknown": 3,
        "review": 1,
        "gap": 2,
        "info": 1,
    }
    assert len(after["changes"]) == 6
    microsoft = next(c for c in after["changes"] if c["key"] == "microsoft")
    assert microsoft["before"]["status"] == "met"
    assert microsoft["after"]["status"] == "review"
    assert len(microsoft["after"]["evidence"]) == 2
    assert after["closed"] is True


def test_only_dependent_assessment_recalculates(client):
    client.get("/api/opportunities/a2-26-38")
    profile = client.get("/api/profile").json()
    profile["facts"]["problem_management"] = {
        "value": True,
        "evidence": "Product specification page 12 confirms problem management.",
    }
    assert client.put("/api/profile", json=profile).status_code == 200
    result = client.get("/api/opportunities/a2-26-38").json()["assessment"]
    assert result["cache"] == {"reused": 11, "evaluated": 1}
    assert result["counts"]["blocker"] == 0
    assert client.get("/api/opportunities/a2-26-38").json()["assessment"]["cache"]["evaluated"] == 0


def test_evidence_removed_returns_to_unknown(client):
    profile = client.get("/api/profile").json()
    profile["facts"]["cmdb"]["evidence"] = ""
    client.put("/api/profile", json=profile)
    cmdb = next(
        r
        for r in client.get("/api/opportunities/a2-26-38").json()["assessment"]["requirements"]
        if r["key"] == "cmdb"
    )
    assert cmdb["status"] == "unknown"


def test_version_scoped_correction_and_audit(client):
    payload = {
        "importance": "preferred",
        "reason": "Reviewer interpretation based on procurement clarification.",
    }
    assert (
        client.post("/api/requirements/microsoft-v0/corrections", json=payload).status_code == 200
    )
    before = client.get("/api/opportunities/a2-26-38?stage=0").json()
    after = client.get("/api/opportunities/a2-26-38").json()
    old = next(r for r in before["assessment"]["requirements"] if r["key"] == "microsoft")
    new = next(r for r in after["assessment"]["requirements"] if r["key"] == "microsoft")
    assert old["importance"] == "preferred"
    assert new["importance"] == "mandatory" and new["status"] == "review"
    assert new["correction"] is None
    event = client.get("/api/audit").json()[0]
    assert event["action"] == "requirement_corrected"
    assert event["detail"]["scope"] == "This exact requirement version only"


def test_profile_rejects_stale_writes_and_incorrect_types(client):
    profile = client.get("/api/profile").json()
    assert client.put("/api/profile", json=profile).status_code == 200
    assert client.put("/api/profile", json=profile).status_code == 409
    profile = client.get("/api/profile").json()
    profile["facts"]["cmdb"]["value"] = 1
    assert client.put("/api/profile", json=profile).status_code == 422
    profile["facts"]["cmdb"]["value"] = "true"
    assert client.put("/api/profile", json=profile).status_code == 422


def test_wrong_version_missing_page_and_short_correction(client):
    assert client.get("/api/opportunities/a2-26-38?stage=42").status_code == 400
    assert client.get("/api/documents/26-38-original/pages/999").status_code == 404
    assert client.get("/api/opportunities/absent").status_code == 404
    assert (
        client.post(
            "/api/requirements/forms-v0/corrections",
            json={"importance": "preferred", "reason": " " * 20},
        ).status_code
        == 422
    )


def test_cross_origin_mutations_rejected(client):
    response = client.put(
        "/api/profile",
        headers={"origin": "https://evil.example"},
        json=client.get("/api/profile").json(),
    )
    assert response.status_code == 403


def test_service_token_is_enforced_when_configured(client, monkeypatch):
    monkeypatch.setenv("BIDLENS_API_TOKEN", "test-only-token")
    assert client.get("/api/health").status_code == 401
    assert (
        client.get("/api/health", headers={"Authorization": "Bearer test-only-token"}).status_code
        == 200
    )


def test_live_import_is_explicitly_unavailable_without_key(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert client.get("/api/health").json()["live_extraction"] is False
    assert (
        client.post(
            "/api/import/url",
            json={
                "url": "https://www.a2gov.org/file.pdf",
                "title": "Test RFP",
                "agency": "Test City",
            },
        ).status_code
        == 503
    )
