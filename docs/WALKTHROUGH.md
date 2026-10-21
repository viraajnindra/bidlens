# Five-minute Loom walkthrough

Run the app and use the fictional Northstar Civic profile. If you changed it during testing, set Problem Management back to No before recording. Keep the official source PDF and this repository open in neighboring tabs.

## 0:00–0:40 — The problem and choice

“A small contractor can spend days on a government proposal before discovering a requirement they cannot meet. Then a 50-page amendment can change the answer. I built BidLens to answer two connected questions: should we spend time on this bid, and did the buyer's changes affect that decision?

I chose this because the valuable part isn't another summary. It's connecting a specific requirement to a company's evidence and making uncertainty visible.”

Show the qualification screen. Point out the historical deadline, real public source, and fictional company label.

## 0:40–1:30 — Show the first decision

Select **Original RFP**.

“The original has five requirements that appear met, two that need confirmation, and one preference gap in my selected review set. I separate a capability the company lacks from a capability we haven't verified. Unknown is not failure, and a preference is not a mandatory blocker.”

Click a source citation and show the highlighted quote and original PDF option.

“Every finding has a page and exact passage. This isn't an exhaustive compliance review: I explicitly show the coverage and preserve the original documents.”

## 1:30–2:30 — Show the real amendment surprise

Switch to **With addenda**, then **What changed?**.

“Problem Management is explicitly named in the amendment. Our sample company doesn't offer it, so it becomes a potential blocker. More interestingly, Answer 5 says SCCM or Intune, but Answer 9 lists both as required. I don't assume the later paragraph magically wins. I show both and flag it for clarification.”

Open page 2 and page 3 citations. Point out that offshore delivery is a preference gap, not a blocker. Migration scope is clarified but still needs a human delivery review.

## 2:30–3:15 — Close the loop

Open **Company profile**. Change Problem Management to Yes and enter an example supporting product specification. Save and return to qualification.

“That resolves this company gap without resolving the unrelated source conflict. The assessment is deterministic once the requirement is reviewed. Cache keys depend on the specific facts used in each comparison, so only affected findings are recalculated.”

Show **Review history** and export the cited review.

## 3:15–4:15 — Architecture and hard parts

Show the README diagram and Source library.

“FastAPI handles the API; a separate worker handles PDFs and model extraction. The database stores durable jobs, source hashes, page text, requirement versions, human reviews, and assessments. SQLite makes the demo easy to run; Compose uses PostgreSQL.

Live imports use Structured Outputs, but a schema isn't enough. Every quote must actually occur on its cited page. Invalid quotations fail the job. A reviewer maps capabilities and amendment replacements before automatic comparison. Scanned or partly unreadable files fail visibly unless OCR is configured.

The hard part was preserving meaning—mandatory versus preferred, missing versus failed, replacement versus clarification—rather than just detecting changed words.”

If no API key is configured, say so: “The demo uses reviewed real-source annotations; the live provider boundary is covered with mocks, not a claimed paid model run.”

## 4:15–5:00 — Verification and another week

Show the tests and verification notes.

“I tested the consequences: source conflicts stay open, missing evidence doesn't become a false rejection, stale saves are rejected, and a reviewed amendment changes the correct requirement while preserving its original version.

With another week, I'd build a labeled set across more agencies and document styles, add OCR and table evaluations, suggest amendment mappings for reviewer approval, and pilot it with small vendors. The success measure would be less review time with fewer missed blockers—not how fluent a summary sounds.”

Finish on the GitHub README. Add the recorded Loom URL to the submission; this script is not a substitute for the video.
