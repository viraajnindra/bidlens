import time
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter

from backend.ingest import Extraction, extract, parse_pdf, validate_url
from backend.models import Document, Job, Opportunity, Requirement, Session
from backend.worker import claim, process


def test_url_import_rejects_local_network_and_untrusted_hosts(monkeypatch):
    for url in [
        "http://www.a2gov.org/test.pdf",
        "https://localhost/test.pdf",
        "https://www.a2gov.org.evil.example/test.pdf",
        "https://user:pass@www.a2gov.org/test.pdf",
        "https://www.a2gov.org:8080/test.pdf",
    ]:
        with pytest.raises(ValueError):
            validate_url(url)
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(ValueError):
        validate_url("https://www.a2gov.org/test.pdf")
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 443))])
    validate_url("https://www.a2gov.org/test.pdf")


def test_scanned_or_empty_page_fails_closed(tmp_path):
    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    writer.write(path)
    with pytest.raises(ValueError, match="too little readable text"):
        parse_pdf(path)


def fake_client(quote):
    parsed = Extraction(
        requirements=[
            {
                "title": "Training",
                "importance": "mandatory",
                "category": "Delivery",
                "evidence": [{"page": 1, "quote": quote}],
                "note": "",
            }
        ]
    )
    return SimpleNamespace(
        responses=SimpleNamespace(parse=lambda **kw: SimpleNamespace(output_parsed=parsed))
    )


def test_structured_output_requires_grounded_quote(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    text = "The vendor must provide training for IT staff and system administrators."
    pages = [{"number": 1, "text": text}]
    result = extract(pages, "doc", client=fake_client(text))
    assert result[0]["rule"] is None
    assert result[0]["review_required"] is True
    assert result[0]["evidence"][0]["document_id"] == "doc"
    with pytest.raises(ValueError, match="not grounded"):
        extract(pages, "doc", client=fake_client("The vendor must have five government contracts."))


def add_job(path, id="test-job", **kwargs):
    with Session.begin() as session:
        if not session.get(Opportunity, "test-opp"):
            session.add(
                Opportunity(
                    id="test-opp", title="Test opportunity", agency="Test city", source_url=""
                )
            )
        session.add(
            Job(
                id=id,
                opportunity_id="test-opp",
                status=kwargs.get("status", "queued"),
                payload={"path": str(path), "name": "Test PDF", "url": ""},
                attempts=kwargs.get("attempts", 0),
                updated_at=kwargs.get("updated_at", time.time()),
            )
        )


def test_durable_worker_claims_once_and_commits_grounded_output(client, tmp_path, monkeypatch):
    path = tmp_path / "test.pdf"
    path.write_bytes(b"%PDF-test")
    add_job(path)
    monkeypatch.setattr(
        "backend.worker.parse_pdf",
        lambda p: [{"number": 1, "text": "The vendor must provide staff training."}],
    )
    monkeypatch.setattr(
        "backend.worker.extract",
        lambda pages, doc, **kw: [
            {
                "title": "Training",
                "importance": "mandatory",
                "category": "Delivery",
                "evidence": [{"document_id": doc, "page": 1, "quote": pages[0]["text"]}],
                "rule": None,
                "action": "added",
            }
        ],
    )
    assert claim() == "test-job"
    assert claim() is None
    process("test-job")
    with Session() as session:
        assert session.get(Job, "test-job").status == "completed"
        assert session.get(Document, "doc-test-job").pages[0]["number"] == 1
        assert session.get(Requirement, "doc-test-job-0").body["rule"] is None
    result = client.get("/api/opportunities/test-opp").json()
    assert result["assessment"]["counts"]["unknown"] == 1


def test_worker_failure_is_visible_and_retry_is_bounded(client, tmp_path, monkeypatch):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a pdf")
    add_job(path)
    monkeypatch.setattr(
        "backend.worker.parse_pdf",
        lambda p: (_ for _ in ()).throw(ValueError("Unreadable source PDF")),
    )
    for attempt in range(3):
        assert claim() == "test-job"
        process("test-job")
        if attempt < 2:
            assert client.post("/api/jobs/test-job/retry").status_code == 200
    assert client.post("/api/jobs/test-job/retry").status_code == 409
    job = client.get("/api/jobs").json()[0]
    assert job["attempts"] == 3 and job["status"] == "failed"
    assert job["error"] == "Unreadable source PDF"


def test_expired_worker_lease_is_recovered(client, tmp_path):
    add_job(tmp_path / "x", status="running", attempts=1, updated_at=time.time() - 2000)
    assert claim() == "test-job"
    with Session() as session:
        assert session.get(Job, "test-job").attempts == 2


def test_live_upload_amendment_mapping_end_to_end(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-sent")
    monkeypatch.setenv("OPENAI_MODEL", "mocked-provider")
    text = "The vendor must provide staff training."
    amended = "This replaces the training requirement: the system must include Problem Management."
    monkeypatch.setattr(
        "backend.worker.parse_pdf",
        lambda p: [{"number": 1, "text": amended if b"amended" in p.read_bytes() else text}],
    )
    monkeypatch.setattr(
        "backend.worker.extract",
        lambda pages, doc, **kw: [
            {
                "title": "Training service",
                "importance": "mandatory",
                "category": "Delivery",
                "evidence": [{"document_id": doc, "page": 1, "quote": pages[0]["text"]}],
                "rule": None,
                "review_required": True,
                "action": "added",
            }
        ],
    )
    first = client.post(
        "/api/import/upload",
        data={"title": "Live test RFP", "agency": "Test City"},
        files={"file": ("original.pdf", b"%PDF-original", "application/pdf")},
    )
    assert first.status_code == 202
    opp = first.json()["opportunity_id"]
    process(claim())
    original = client.get(f"/api/opportunities/{opp}").json()["assessment"]["requirements"][0]
    assert original["status"] == "unknown"
    mapped = client.post(
        f"/api/requirements/{original['id']}/mapping",
        json={
            "field": "training",
            "reason": "The original explicitly requires staff training.",
        },
    )
    assert mapped.status_code == 200
    assert (
        client.get(f"/api/opportunities/{opp}").json()["assessment"]["requirements"][0]["status"]
        == "met"
    )
    second = client.post(
        "/api/import/upload",
        data={"title": "Live test RFP", "agency": "Test City", "opportunity_id": opp},
        files={"file": ("amendment.pdf", b"%PDF-amended", "application/pdf")},
    )
    assert second.status_code == 202
    process(claim())
    detail = client.get(f"/api/opportunities/{opp}").json()
    assert len(detail["assessment"]["requirements"]) == 2  # No guessed precedence.
    amendment = next(r for r in detail["assessment"]["requirements"] if r["sequence"] == 1)
    options = client.get(f"/api/requirements/{amendment['id']}/review-options").json()
    assert options["previous"][0]["key"] == original["key"]
    result = client.post(
        f"/api/requirements/{amendment['id']}/mapping",
        json={
            "field": "problem_management",
            "supersedes_key": original["key"],
            "reason": "Test fixture: a reviewer explicitly confirms a replacement and capability mapping.",
        },
    )
    assert result.status_code == 200
    detail = client.get(f"/api/opportunities/{opp}").json()
    assert len(detail["assessment"]["requirements"]) == 1
    assert detail["assessment"]["counts"]["blocker"] == 1
    assert detail["changes"][0]["before"]["status"] == "met"
    assert detail["changes"][0]["after"]["status"] == "blocker"
    assert detail["changes"][0]["type"] == "replaced"
    assert (
        client.get(f"/api/opportunities/{opp}?stage=0").json()["assessment"]["counts"]["met"] == 1
    )
    assert client.get(f"/api/documents/{detail['documents'][0]['id']}/pdf").status_code == 200


def test_bad_upload_is_rejected_without_job(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    for content in [b"", b"not a PDF"]:
        response = client.post(
            "/api/import/upload",
            data={"title": "Invalid file", "agency": "Test city"},
            files={"file": ("bad.pdf", content, "application/pdf")},
        )
        assert response.status_code == 422
    assert client.get("/api/jobs").json() == []


def test_demo_cannot_be_mutated_by_live_mapping_or_amendment(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    assert (
        client.post(
            "/api/requirements/cmdb-v0/mapping",
            json={"field": "cmdb", "reason": "A sufficiently detailed explanation"},
        ).status_code
        == 409
    )
    response = client.post(
        "/api/import/upload",
        data={"title": "An amendment", "agency": "Test City", "opportunity_id": "a2-26-38"},
        files={"file": ("x.pdf", b"%PDF-test", "application/pdf")},
    )
    assert response.status_code == 409


def test_short_text_only_exhibit_divider_is_valid(tmp_path):
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 50 50 Td (EXHIBIT B Compensation) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    path = tmp_path / "divider.pdf"
    writer.write(path)
    assert parse_pdf(path)[0]["text"] == "EXHIBIT B Compensation"


def test_failed_job_can_be_dismissed_without_losing_audit(client, tmp_path):
    add_job(tmp_path / "unused.pdf", status="failed", attempts=3)
    assert client.post("/api/jobs/test-job/dismiss").status_code == 200
    assert client.get("/api/jobs").json()[0]["status"] == "dismissed"
    assert client.get("/api/audit").json()[0]["action"] == "failed_import_dismissed"
    assert client.post("/api/jobs/test-job/retry").status_code == 409
