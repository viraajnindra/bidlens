# Architecture and decisions

## The product boundary

The user is a small government contractor deciding whether to invest in a proposal and how an amendment changes that decision. The useful output is a source-backed review task, not an unexplained fit score. A score can hide a single blocker among many easy requirements.

The two screens share one model: a versioned requirement, its evidence, a comparison against company facts, and the reason for a change. This keeps the project deeper than a collection of unrelated contract features.

## Components

| Component | Responsibility |
| --- | --- |
| `frontend/app/page.tsx` | Qualification, changes, profile, source viewer, import queue, review dialogs |
| `backend/app.py` | API validation, profile concurrency control, reviewer actions, import queueing |
| `backend/engine.py` | Requirement snapshots, deterministic assessment, dependency cache, semantic change records |
| `backend/ingest.py` | Restricted downloads, bounded PDF parsing, structured extraction, citation validation |
| `backend/worker.py` | Durable claiming, heartbeats, crash recovery, transactional publication, bounded retries |
| `backend/models.py` | SQLAlchemy schema and configuration |
| `data/demo.json` | Reproducible real-source text and selected reviewed annotations |

The frontend calls a same-origin Next.js rewrite. The API and worker share a database and document directory. Slow PDF/model work happens in the worker, not the HTTP request. No message broker is needed for a single-user prototype.

## Data lifecycle

1. An import creates an opportunity (or uses an existing live opportunity), reserves its document sequence in a queued job, and returns immediately.
2. The worker claims the job with a conditional database update. Attempts are bounded to three. A heartbeat renews its lease before each model batch; a worker crash can be recovered after 30 minutes.
3. PDF bytes receive a SHA-256 digest. Re-importing identical bytes into the same opportunity fails visibly.
4. Text retains PDF page numbers. Encrypted, oversized, empty, or partly unreadable documents are rejected. Text is processed in four-page batches, with incomplete boundary context explicitly left for review.
5. Structured Outputs constrain the model response. Each citation must match text on the cited page after whitespace normalization. A failed citation rejects the entire extraction rather than publishing ungrounded findings.
6. The document and requirements are committed together. Until a reviewer maps them, live findings are independent and have no automatic company comparison. Mandatory findings therefore remain unresolved.
7. A reviewer may map a supported boolean capability and explicitly link an amendment finding to an earlier requirement. These decisions append `MappingReview` and `Audit` records. Source text and raw extraction stay unchanged.
8. At a given document sequence, the engine selects the latest version for each reviewed requirement lineage. It applies classification corrections only to the exact version corrected.
9. Assessments compare the selected requirement with relevant company facts. “Unknown” means missing evidence; “blocker” means affirmative evidence of a mandatory mismatch. Source conflict takes precedence over every classification.

## Why human-reviewed mappings?

A semantically similar paragraph is not necessarily a replacement. An amendment could clarify a different subsystem or a different project phase. Automatically treating similarity as legal precedence would create confident but incorrect advice.

The real example has an explicit precedence statement between documents, but two answers *within the same addendum* disagree about integrations. Later page order alone is not treated as authority. Both citations are shown and the result remains open for buyer clarification.

The demo encodes those reviewed mappings. Live imports expose the review step directly. A future model can suggest mappings, but should not silently approve them.

## Incremental assessment

The SHA-256 cache fingerprint includes:

- Engine version.
- Immutable requirement ID and effective reviewed body.
- Version-scoped correction ID, when present.
- Values and evidence for only the company facts used by that requirement.

Changing Problem Management re-evaluates one comparison. Changing an unrelated planning quantity re-evaluates none. Removing supporting evidence returns a previously positive answer to unknown. A changed profile name does not invalidate semantic results.

Both sides of the change view use the **same current company profile**. Comparing an old profile to a new one would conflate a document change with a company change. The UI states this explicitly.

## Failure handling and boundaries

- SQLite is the simple local default; PostgreSQL is the Compose configuration. Database writes are transactional. Profiles use version checks to prevent stale saves. Cache writes ignore identical concurrent insertions.
- Jobs surface failures rather than silently substituting demo data. Provider error details are sanitized to avoid exposing request contents or credentials.
- URL imports use exact configured hostnames, HTTPS, public IP checks, bounded streamed downloads, and no redirects. This is an allowlist for trusted government hosts, not a general-purpose arbitrary URL fetcher.
- Extraction prompts treat PDF content as untrusted data. Generated content is rendered as text, never HTML. The model does not get tool access or decide eligibility.
- The local API rejects unexpected cross-origin writes. Public hosting would require real user authentication, isolated workspaces, upload quotas, malware/content scanning appropriate to deployment, and rate controls.
- Source quotation validation is not a proof of correct interpretation or completeness. The UI and README distinguish these claims.

## Deliberate tradeoffs

No vector database: exact citations and explicit lineage solve this prototype's central problem; embeddings alone cannot establish precedence. No generated bid prose: a convincing paragraph is less useful than recognizing an unsupported requirement. No fake ROI: the next step is to measure avoided review work and missed requirements with real vendors.
