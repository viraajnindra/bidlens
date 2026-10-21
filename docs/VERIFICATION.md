# Verification record

Verified locally on October 21, 2026 using Python 3.12 and Node.js 24.

| Check | Result |
| --- | --- |
| Backend tests | **35 passed**, 88% statement coverage |
| Rule engine | 97% statement coverage; missing evidence, preferences, conflicts, and cache invalidation covered |
| API | 90% statement coverage; validation, stale saves, reviews, imports, and audit events covered |
| TypeScript / production Next.js build | Passed |
| GitHub Actions | Backend and frontend checks passed on the published repository |
| Python lint and formatting | Passed |
| Frontend formatting | Passed |
| Official PDF integrity | Both source SHA-256 hashes verified; 35 + 50 pages extracted successfully |
| One-command local startup | API, worker, and frontend start successfully together |
| Browser qualification flow | Original versus amended counts verified |
| Browser profile update | Problem Management changed to Yes with evidence; blocker resolved; profile restored for demo |
| Browser evidence | Exact quotation and correct page displayed; official source link verified |
| Browser export | Markdown review downloaded successfully |
| Responsive layout | 390 px viewport inspected; document width equals viewport width (no horizontal overflow) |
| Compose configuration | `docker compose config --quiet` passed |

## What is mocked or unverified

- **OpenAI provider calls are mocked in automated tests.** No API key was configured for a paid live extraction. The end-to-end integration test exercises upload, persisted job, extraction boundary, original review, amendment review, source retrieval, and changed assessment with a mocked provider. It does not establish model accuracy on unseen documents.
- **Docker/PostgreSQL runtime was not exercised locally** because the Docker engine was not running. Compose configuration validates; the SQLite path is the verified quickstart.
- **Optional Docling OCR was not installed or exercised.** The default text-PDF path is tested, including a regression for valid short exhibit-divider pages. The OCR exporter follows the [Docling page-specific text export API](https://docling-project.github.io/docling/reference/docling_document/#docling_core.types.doc.DoclingDocument.export_to_text).
- Tests report one upstream Starlette/httpx deprecation warning; assertions pass.
- This is not a formal accessibility audit, security audit, extraction-quality benchmark, or proof of production scalability.

## Expected untouched demo results

| Stage | Appears met | Potential blocker | Needs confirmation | Source conflict | Preference gap | Context |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original | 5 | 0 | 2 | 0 | 1 | 0 |
| With Addendum 1 | 4 | 1 | 3 | 1 | 2 | 1 |

These are expectations for the selected reviewed subset and the fictional default company—not for all clauses in the procurement.
