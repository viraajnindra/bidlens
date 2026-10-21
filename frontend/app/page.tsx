"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileCheck2,
  FileText,
  Fingerprint,
  GitCompareArrows,
  History,
  Layers3,
  Loader2,
  Plus,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Upload,
  X,
} from "lucide-react";

type Cite = { document_id: string; page: number; quote: string };
type Fact = { value: boolean | number | null; evidence: string };
type Requirement = {
  id: string;
  key: string;
  title: string;
  importance: string;
  category: string;
  status: string;
  reason: string;
  evidence: Cite[];
  note?: string;
  change_reason?: string;
  correction?: { reason: string; importance: string };
  company_evidence: Record<string, Fact>;
  review_required?: boolean;
  mapping_reviewed?: boolean;
  rule?: { fields: string[] } | null;
  supersedes_key?: string | null;
  conflict?: boolean;
};
type Change = {
  key: string;
  type: string;
  title: string;
  explanation: string;
  before: Requirement | null;
  after: Requirement | null;
  status_changed: boolean;
};
type Doc = {
  id: string;
  name: string;
  sequence: number;
  pages: number;
  url: string;
  sha256: string;
  mode: string;
  pdf_available: boolean;
};
type Opportunity = {
  id: string;
  title: string;
  agency: string;
  description: string;
  source_url: string;
  closed: boolean | null;
  mode: string;
  deadline: string | null;
};
type Detail = Opportunity & {
  documents: Doc[];
  latest_stage: number;
  original_counts: Record<string, number>;
  assessment: {
    requirements: Requirement[];
    counts: Record<string, number>;
    verdict: string;
    stage: number;
    profile_version: number;
    cache: { reused: number; evaluated: number };
  };
  changes: Change[];
};
type Profile = {
  name: string;
  version: number;
  facts: Record<string, Fact>;
  fields: { key: string; label: string; type: string }[];
};
type Job = {
  id: string;
  opportunity_id: string;
  status: string;
  attempts: number;
  error: string | null;
};
type Audit = {
  id: string;
  created_at: number;
  action: string;
  detail: Record<string, unknown>;
};
const labels: Record<string, string> = {
  met: "Appears met",
  blocker: "Potential blocker",
  unknown: "Needs confirmation",
  review: "Source conflict",
  gap: "Preference gap",
  info: "Context",
};
const statusOrder = ["blocker", "review", "unknown", "gap", "met", "info"];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${res.status}). Check the input and try again.`,
    );
  }
  return res.json();
}
function Badge({ status }: { status: string }) {
  return (
    <span className={`badge ${status}`}>
      <span className="status-dot" />
      {labels[status] || status}
    </span>
  );
}
function Highlight({ text, quote }: { text: string; quote: string }) {
  const normalized = text.replace(/\s+/g, " ").trim();
  const q = quote.replace(/\s+/g, " ").trim();
  const index = normalized.indexOf(q);
  return (
    <div className="page-text">
      {index < 0 ? (
        normalized
      ) : (
        <>
          {normalized.slice(0, index)}
          <mark>{normalized.slice(index, index + q.length)}</mark>
          {normalized.slice(index + q.length)}
        </>
      )}
    </div>
  );
}

export default function Home() {
  const [tab, setTab] = useState("qualify");
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [selected, setSelected] = useState("a2-26-38");
  const [stage, setStage] = useState<number | undefined>();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [health, setHealth] = useState<{ live_extraction: boolean } | null>(
    null,
  );
  const [jobs, setJobs] = useState<Job[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [evidence, setEvidence] = useState<{
    cite: Cite;
    requirement: Requirement;
  } | null>(null);
  const [page, setPage] = useState<{
    text: string;
    name: string;
    url: string;
    pdf_available: boolean;
  } | null>(null);
  const [pdfView, setPdfView] = useState(false);
  const [correction, setCorrection] = useState<Requirement | null>(null);
  const [reason, setReason] = useState("");
  const [importance, setImportance] = useState("mandatory");
  const [busy, setBusy] = useState(false);
  const [sourceUrl, setSourceUrl] = useState("");
  const [importTitle, setImportTitle] = useState("");
  const [agency, setAgency] = useState("");
  const [upload, setUpload] = useState<File | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const mappingDialog = useRef<HTMLDialogElement>(null);
  const [mapping, setMapping] = useState<Requirement | null>(null);
  const [mappingOptions, setMappingOptions] = useState<{
    previous: { key: string; title: string }[];
    fields: { key: string; label: string }[];
  }>({ previous: [], fields: [] });
  const [mapField, setMapField] = useState("");
  const [mapPrevious, setMapPrevious] = useState("");
  const [mapConflict, setMapConflict] = useState(false);
  const [mapReason, setMapReason] = useState("");
  const [importTarget, setImportTarget] = useState("");
  useEffect(() => {
    if (mapping) mappingDialog.current?.showModal();
    else mappingDialog.current?.close();
  }, [mapping]);
  async function openMapping(r: Requirement) {
    try {
      setMappingOptions(await api(`/requirements/${r.id}/review-options`));
      setMapField(r.rule?.fields[0] || "");
      setMapPrevious(r.supersedes_key || "");
      setMapConflict(!!r.conflict);
      setMapReason(r.mapping_reviewed ? r.change_reason || "" : "");
      setMapping(r);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function saveMapping(e: React.FormEvent) {
    e.preventDefault();
    if (!mapping) return;
    setBusy(true);
    try {
      await api(`/requirements/${mapping.id}/mapping`, {
        method: "POST",
        body: JSON.stringify({
          field: mapField || null,
          supersedes_key: mapPrevious || null,
          conflict: mapConflict,
          reason: mapReason,
        }),
      });
      setMapping(null);
      await loadDetail();
      setAudit(await api<Audit[]>("/audit"));
      setNotice(
        "Mapping reviewed. The source, interpretation, and assessment are linked.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const loadDetail = useCallback(async () => {
    const d = await api<Detail>(
      `/opportunities/${selected}${stage === undefined ? "" : `?stage=${stage}`}`,
    );
    setDetail(d);
  }, [selected, stage]);
  const refreshBase = useCallback(async () => {
    const [o, p, h, j, a] = await Promise.all([
      api<Opportunity[]>("/opportunities"),
      api<Profile>("/profile"),
      api<{ live_extraction: boolean }>("/health"),
      api<Job[]>("/jobs"),
      api<Audit[]>("/audit"),
    ]);
    setOpportunities(o);
    setProfile(p);
    setHealth(h);
    setJobs(j);
    setAudit(a);
  }, []);
  useEffect(() => {
    refreshBase().catch((e) => setError(e.message));
  }, [refreshBase]);
  useEffect(() => {
    let current = true;
    setLoading(true);
    setError("");
    api<Detail>(
      `/opportunities/${selected}${stage === undefined ? "" : `?stage=${stage}`}`,
    )
      .then((d) => {
        if (current) setDetail(d);
      })
      .catch((e) => {
        if (current) setError(e.message);
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [selected, stage]);
  useEffect(() => {
    if (!jobs.some((j) => ["queued", "running"].includes(j.status))) return;
    const id = setInterval(() => {
      api<Job[]>("/jobs")
        .then((j) => {
          setJobs(j);
          if (j.some((x) => x.status === "completed")) {
            api<Opportunity[]>("/opportunities").then(setOpportunities);
            loadDetail().catch(() => {});
          }
        })
        .catch((e) => setError(e.message));
    }, 3000);
    return () => clearInterval(id);
  }, [jobs, loadDetail]);
  useEffect(() => {
    if (!evidence) {
      setPage(null);
      return;
    }
    let active = true;
    setPage(null);
    setPdfView(false);
    api<{ text: string; name: string; url: string; pdf_available: boolean }>(
      `/documents/${evidence.cite.document_id}/pages/${evidence.cite.page}`,
    )
      .then((p) => {
        if (active) setPage(p);
      })
      .catch((e) => setError(e.message));
    return () => {
      active = false;
    };
  }, [evidence]);
  useEffect(() => {
    if (correction) dialog.current?.showModal();
    else dialog.current?.close();
  }, [correction]);
  useEffect(() => {
    if (!notice) return;
    const id = setTimeout(() => setNotice(""), 7000);
    return () => clearTimeout(id);
  }, [notice]);
  async function saveProfile() {
    if (!profile) return;
    setBusy(true);
    setError("");
    try {
      const p = await api<Profile>("/profile", {
        method: "PUT",
        body: JSON.stringify(profile),
      });
      setProfile(p);
      await loadDetail();
      setAudit(await api<Audit[]>("/audit"));
      setNotice(
        "Company profile saved. Affected comparisons have been recalculated.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function saveCorrection() {
    if (!correction) return;
    setBusy(true);
    try {
      await api(`/requirements/${correction.id}/corrections`, {
        method: "POST",
        body: JSON.stringify({ importance, reason }),
      });
      setCorrection(null);
      await loadDetail();
      setAudit(await api<Audit[]>("/audit"));
      setNotice(
        "Correction saved to this requirement version. The original source is preserved.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function importPdf(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      let result: { job_id: string; opportunity_id: string };
      if (upload) {
        const form = new FormData();
        form.append("title", importTitle);
        form.append("agency", agency);
        form.append("file", upload);
        if (importTarget) form.append("opportunity_id", importTarget);
        result = await api("/import/upload", { method: "POST", body: form });
      } else {
        result = await api("/import/url", {
          method: "POST",
          body: JSON.stringify({
            title: importTitle,
            agency,
            url: sourceUrl,
            opportunity_id: importTarget || null,
          }),
        });
      }
      setJobs(await api<Job[]>("/jobs"));
      setOpportunities(await api<Opportunity[]>("/opportunities"));
      setNotice(
        `Document queued. Keep the worker running to process it. Job ${result.job_id.slice(0, 8)}.`,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function downloadBrief() {
    if (!detail) return;
    const content = [
      `# BidLens review: ${detail.title}`,
      `Agency: ${detail.agency}`,
      `Historical deadline: ${detail.deadline || "Not verified"}`,
      `Company: ${profile?.name}`,
      `Source: ${detail.source_url}`,
      "",
      "Selected requirements only. This is a decision aid, not a complete compliance certification.",
      "",
      ...detail.assessment.requirements.flatMap((r) => [
        `## ${r.title}`,
        `${labels[r.status]} · ${r.importance}`,
        r.reason,
        ...r.evidence.map(
          (c) =>
            `> ${c.quote}\n\nSource: ${detail.documents.find((d) => d.id === c.document_id)?.url || c.document_id} — PDF page ${c.page}`,
        ),
        "",
      ]),
    ].join("\n");
    const url = URL.createObjectURL(
      new Blob([content], { type: "text/markdown" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "bidlens-review.md";
    a.click();
    URL.revokeObjectURL(url);
  }
  const requirements = (detail?.assessment.requirements || [])
    .filter(
      (r) =>
        (filter === "all" || r.status === filter) &&
        `${r.title} ${r.category} ${r.evidence.map((e) => e.quote).join(" ")}`
          .toLowerCase()
          .includes(query.toLowerCase()),
    )
    .sort(
      (a, b) => statusOrder.indexOf(a.status) - statusOrder.indexOf(b.status),
    );
  const nav = [
    { id: "qualify", label: "Should we bid?", icon: FileCheck2 },
    { id: "changes", label: "What changed?", icon: GitCompareArrows },
    { id: "profile", label: "Company profile", icon: SlidersHorizontal },
    { id: "sources", label: "Source library", icon: BookOpen },
  ];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="BidLens home">
          <span className="brand-icon">
            <Layers3 size={22} />
          </span>
          BidLens<span className="brand-period">.</span>
        </a>
        <div className="workspace-label">PROCUREMENT WORKSPACE</div>
        <nav aria-label="Main navigation">
          {nav.map((n) => (
            <button
              key={n.id}
              className={`nav-item ${tab === n.id ? "active" : ""}`}
              onClick={() => {
                setTab(n.id);
                setEvidence(null);
              }}
            >
              <n.icon size={19} />
              {n.label}
              {n.id === "changes" && !!detail?.changes.length && (
                <span className="nav-count">{detail.changes.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-case">
          <span className="eyebrow">IN YOUR WORKSPACE</span>
          <label htmlFor="opportunity-select" className="sr-only">
            Select opportunity
          </label>
          <select
            id="opportunity-select"
            value={selected}
            onChange={(e) => {
              setSelected(e.target.value);
              setStage(undefined);
              setEvidence(null);
            }}
          >
            {opportunities.map((o) => (
              <option key={o.id} value={o.id}>
                {o.id === "a2-26-38" ? "Ann Arbor · RFP 26-38" : o.title}
              </option>
            ))}
          </select>
          <p>Every decision starts with evidence.</p>
        </div>
        <div className="sidebar-bottom">
          <button
            className={`nav-item ${tab === "activity" ? "active" : ""}`}
            onClick={() => setTab("activity")}
          >
            <History size={18} />
            Review history
          </button>
          <div className="demo-label">
            <span className="status-dot" />{" "}
            {health?.live_extraction
              ? "Live extraction enabled"
              : "Reviewed demo"}
            <span className="small">Local, single-user workspace</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={14} />
            <span>
              {tab === "activity"
                ? "Review history"
                : nav.find((n) => n.id === tab)?.label}
            </span>
          </div>
          <div className="topbar-right">
            <button
              className="mobile-history icon-button"
              aria-label="Review history"
              onClick={() => setTab("activity")}
            >
              <History size={17} />
            </button>
            <span className="verified">
              <ShieldCheck size={15} />
              Evidence first
            </span>
            <span className="avatar">NC</span>
          </div>
        </header>
        <main>
          {error && (
            <div className="error-banner" role="alert">
              {error}
              <button onClick={() => setError("")} aria-label="Dismiss error">
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="notice" role="status">
              <Check size={17} />
              {notice}
            </div>
          )}
          {(tab === "qualify" || tab === "changes") && (
            <>
              <div className="heading-row">
                <div>
                  <div className="eyebrow teal">
                    {tab === "qualify"
                      ? "01 / BID QUALIFICATION"
                      : "02 / AMENDMENT INTELLIGENCE"}
                  </div>
                  <h1>
                    {tab === "qualify"
                      ? "A clearer path to your next bid."
                      : "Small changes. Real consequences."}
                  </h1>
                  <p className="subtitle">
                    {tab === "qualify"
                      ? "Know what fits, what’s missing, and what needs a second look."
                      : "See what the buyer changed—and what it means for your team."}
                  </p>
                </div>
                <button
                  className="button secondary export-button"
                  onClick={downloadBrief}
                  disabled={!detail}
                >
                  <ArrowDownToLine size={16} />
                  Export review
                </button>
              </div>
              {loading ? (
                <div className="loading">
                  <Loader2 className="spin" />
                  Reading the evidence…
                </div>
              ) : (
                detail && (
                  <>
                    <section className="opportunity-card">
                      <div className="opportunity-main">
                        <div className="opportunity-meta">
                          <span className="rfp-tag">
                            {detail.id === "a2-26-38"
                              ? "RFP 26-38"
                              : "IMPORTED RFP"}
                          </span>
                          <span>{detail.agency}</span>
                          {detail.closed && (
                            <span className="historical">
                              <Clock3 size={12} />
                              Historical · closed
                            </span>
                          )}
                        </div>
                        <h2>{detail.title}</h2>
                        <p>{detail.description}</p>
                        <div className="opportunity-bottom">
                          <span>
                            <FileText size={14} />
                            {detail.documents.length} documents ·{" "}
                            {detail.documents.reduce((n, d) => n + d.pages, 0)}{" "}
                            pages
                          </span>
                          <span>
                            <ShieldCheck size={14} />
                            {detail.mode === "reviewed_demo"
                              ? "Selected, curated annotations"
                              : "AI extracted · needs review"}
                          </span>
                          {detail.source_url && (
                            <a
                              href={detail.source_url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Official source <ArrowUpRight size={13} />
                            </a>
                          )}
                        </div>
                      </div>
                      <div className="case-note">
                        <span className="eyebrow">
                          {detail.closed
                            ? "PAST SUBMISSION DEADLINE"
                            : "SUBMISSION DEADLINE"}
                        </span>
                        <strong>
                          {detail.deadline
                            ? new Date(detail.deadline).toLocaleDateString(
                                "en-US",
                                {
                                  month: "short",
                                  day: "numeric",
                                  year: "numeric",
                                },
                              )
                            : "Not verified"}
                        </strong>
                        <span>
                          {detail.id === "a2-26-38"
                            ? "2:00 PM · Ann Arbor local time"
                            : "Verify in the source documents"}
                        </span>
                      </div>
                    </section>
                    {tab === "qualify" ? (
                      <>
                        <div className="assessment-toolbar">
                          <div className="section-title">
                            Company fit{" "}
                            <span>
                              for{" "}
                              {profile?.name.split(" · ")[0] || "your company"}
                            </span>
                          </div>
                          <div
                            className="segmented"
                            role="group"
                            aria-label="Document version"
                          >
                            <button
                              className={
                                detail.assessment.stage === 0 ? "selected" : ""
                              }
                              onClick={() => setStage(0)}
                            >
                              Original RFP
                            </button>
                            <button
                              disabled={detail.latest_stage === 0}
                              className={
                                detail.assessment.stage > 0 ? "selected" : ""
                              }
                              onClick={() => setStage(undefined)}
                            >
                              With addenda <span>{detail.latest_stage}</span>
                            </button>
                          </div>
                        </div>
                        <div className="stats-grid">
                          {[
                            {
                              key: "blocker",
                              label: "Potential blockers",
                              hint: "Address before proceeding",
                            },
                            {
                              key: "review",
                              label: "Source conflicts",
                              hint: "Get clarification from the buyer",
                            },
                            {
                              key: "unknown",
                              label: "Need confirmation",
                              hint: "Gather the missing evidence",
                            },
                            {
                              key: "met",
                              label: "Appear met",
                              hint: "Backed by company evidence",
                            },
                          ].map((s) => (
                            <button
                              key={s.key}
                              className={`stat-card ${s.key} ${filter === s.key ? "stat-selected" : ""}`}
                              onClick={() =>
                                setFilter(filter === s.key ? "all" : s.key)
                              }
                            >
                              <span>
                                {s.label}
                                <ArrowUpRight size={14} />
                              </span>
                              <strong>{detail.assessment.counts[s.key]}</strong>
                              <small>{s.hint}</small>
                            </button>
                          ))}
                        </div>
                        <div className="verdict-strip">
                          <div>
                            <span className="verdict-icon">
                              <CircleHelp size={18} />
                            </span>
                            <strong>{detail.assessment.verdict}</strong>
                            <span>
                              Based on {detail.assessment.requirements.length}{" "}
                              selected requirements. Review the full RFP before
                              deciding.
                            </span>
                          </div>
                          <span
                            className="cache-note"
                            title="Results are cached by requirement version and the specific company facts used in its comparison."
                          >
                            {detail.assessment.cache.reused} reused ·{" "}
                            {detail.assessment.cache.evaluated} recalculated
                          </span>
                        </div>
                        <div className="requirements-layout">
                          <section className="requirements-panel">
                            <div className="panel-header">
                              <h3>Requirement review</h3>
                              <span className="count-chip">
                                {requirements.length}
                              </span>
                              <div className="search">
                                <Search size={15} />
                                <input
                                  aria-label="Search requirements"
                                  placeholder="Search requirements…"
                                  value={query}
                                  onChange={(e) => setQuery(e.target.value)}
                                />
                              </div>
                            </div>
                            <div className="filter-row">
                              <button
                                className={filter === "all" ? "selected" : ""}
                                onClick={() => setFilter("all")}
                              >
                                All requirements
                              </button>
                              {["blocker", "review", "unknown", "gap"].map(
                                (s) => (
                                  <button
                                    key={s}
                                    className={filter === s ? "selected" : ""}
                                    onClick={() => setFilter(s)}
                                  >
                                    {labels[s]}{" "}
                                    <span>{detail.assessment.counts[s]}</span>
                                  </button>
                                ),
                              )}
                            </div>
                            {requirements.length === 0 ? (
                              <div className="empty">
                                No requirements match this view. Try another
                                filter.
                              </div>
                            ) : (
                              requirements.map((r) => (
                                <article
                                  className={`requirement-row ${evidence?.requirement.id === r.id ? "focused" : ""}`}
                                  key={r.id}
                                >
                                  <div
                                    className={`requirement-icon ${r.status}`}
                                  >
                                    {r.status === "met" ? (
                                      <Check size={17} />
                                    ) : r.status === "review" ? (
                                      <GitCompareArrows size={17} />
                                    ) : (
                                      <FileText size={17} />
                                    )}
                                  </div>
                                  <div className="requirement-content">
                                    <div className="requirement-heading">
                                      <h4>{r.title}</h4>
                                      <Badge status={r.status} />
                                    </div>
                                    <div className="requirement-meta">
                                      {r.category}
                                      <span>·</span>
                                      <span
                                        className={
                                          r.importance === "mandatory"
                                            ? "mandatory"
                                            : ""
                                        }
                                      >
                                        {r.importance}
                                      </span>
                                      {r.correction && (
                                        <span className="correction-tag">
                                          Reviewed correction
                                        </span>
                                      )}
                                    </div>
                                    <p>{r.reason}</p>
                                    <div className="requirement-actions">
                                      {r.evidence.map((c, i) => (
                                        <button
                                          className="source-link"
                                          key={i}
                                          onClick={() =>
                                            setEvidence({
                                              cite: c,
                                              requirement: r,
                                            })
                                          }
                                        >
                                          <FileText size={12} />
                                          {detail.documents.find(
                                            (d) => d.id === c.document_id,
                                          )?.name || "Source"}{" "}
                                          · p. {c.page}
                                          <ArrowUpRight size={12} />
                                        </button>
                                      ))}
                                      {(r.review_required ||
                                        r.mapping_reviewed) && (
                                        <button
                                          className="source-link"
                                          onClick={() => openMapping(r)}
                                        >
                                          <CheckCheck size={12} />
                                          {r.mapping_reviewed
                                            ? "Edit mapping"
                                            : "Map & verify"}
                                        </button>
                                      )}
                                      <button
                                        className="text-button correct-button"
                                        onClick={() => {
                                          setCorrection(r);
                                          setImportance(r.importance);
                                          setReason("");
                                        }}
                                      >
                                        Review classification
                                      </button>
                                    </div>
                                  </div>
                                </article>
                              ))
                            )}
                          </section>
                          {evidence ? (
                            <EvidencePanel />
                          ) : (
                            <aside className="evidence-placeholder">
                              <div className="lens-graphic">
                                <FileText size={31} />
                                <span>
                                  <Search size={22} />
                                </span>
                              </div>
                              <h3>Don’t take our word for it.</h3>
                              <p>
                                Select any source citation to read the exact
                                passage behind a finding.
                              </p>
                              <div className="mini-divider" />
                              <span>
                                <Fingerprint size={15} />
                                Original documents, traceable findings.
                              </span>
                            </aside>
                          )}
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="changes-intro">
                          <div>
                            <h3>
                              Original RFP <ArrowRight size={18} />{" "}
                              {detail.latest_stage
                                ? `Addendum ${detail.latest_stage}`
                                : "No addendum yet"}
                            </h3>
                            <p>
                              {detail.changes.length} substantive findings in
                              the reviewed set. Both versions use the same
                              current company profile.
                            </p>
                          </div>
                          <span className="pill">
                            {
                              detail.changes.filter((c) => c.status_changed)
                                .length
                            }{" "}
                            affect the assessment
                          </span>
                        </div>
                        <div className="changes-layout">
                          <div className="change-list">
                            {detail.changes.length === 0 && (
                              <div className="empty">
                                No reviewed amendment changes yet. This
                                opportunity has one document version.
                              </div>
                            )}
                            {detail.changes.map((c, i) => (
                              <article
                                className={`change-card ${c.type === "conflict" ? "conflict-card" : ""}`}
                                key={c.key}
                              >
                                <div className="change-topline">
                                  <span className="change-number">
                                    {String(i + 1).padStart(2, "0")}
                                  </span>
                                  <span className={`change-type ${c.type}`}>
                                    {c.type === "conflict"
                                      ? "Conflicting language"
                                      : c.type === "clarified"
                                        ? "Scope clarified"
                                        : c.type === "removed"
                                          ? "Removed"
                                          : c.type === "replaced"
                                            ? "Requirement replaced"
                                            : "Newly documented"}
                                  </span>
                                  {c.after && <Badge status={c.after.status} />}
                                </div>
                                <h3>{c.title}</h3>
                                <p>{c.explanation}</p>
                                <div className="comparison">
                                  <div>
                                    <span className="eyebrow">BEFORE</span>
                                    <p>
                                      {c.before?.title ||
                                        "Not in the selected original requirements"}
                                    </p>
                                    {c.before && (
                                      <Badge status={c.before.status} />
                                    )}
                                  </div>
                                  <ArrowRight size={18} />
                                  <div>
                                    <span className="eyebrow">
                                      AFTER ADDENDUM
                                    </span>
                                    <p>
                                      {c.after?.title || "Explicitly removed"}
                                    </p>
                                    {c.after && (
                                      <Badge status={c.after.status} />
                                    )}
                                  </div>
                                </div>
                                <div className="requirement-actions">
                                  {c.after?.evidence.map((cite, j) => (
                                    <button
                                      className="source-link"
                                      key={j}
                                      onClick={() =>
                                        setEvidence({
                                          cite,
                                          requirement: c.after!,
                                        })
                                      }
                                    >
                                      <FileText size={12} />
                                      {detail.documents.find(
                                        (d) => d.id === cite.document_id,
                                      )?.name || "Source"}{" "}
                                      · p. {cite.page}
                                      <ArrowUpRight size={12} />
                                    </button>
                                  ))}
                                </div>
                              </article>
                            ))}
                          </div>
                          {evidence ? (
                            <EvidencePanel />
                          ) : (
                            <aside className="change-guide">
                              <div className="guide-icon">
                                <GitCompareArrows size={24} />
                              </div>
                              <h3>
                                The document changed.
                                <br />
                                Did your decision?
                              </h3>
                              <p>
                                A word-level diff would show edits. This view
                                connects those edits to requirements and your
                                company’s capabilities.
                              </p>
                              <ol>
                                <li>
                                  <strong>Preserve the original.</strong>Every
                                  requirement keeps its source and version.
                                </li>
                                <li>
                                  <strong>Check the consequence.</strong>
                                  Re-evaluate the facts affected by a change.
                                </li>
                                <li>
                                  <strong>Keep uncertainty visible.</strong>
                                  Conflicting answers stay open for review.
                                </li>
                              </ol>
                              <div className="callout">
                                <BookOpen size={16} />
                                <span>
                                  {detail.mode === "reviewed_demo"
                                    ? "The addendum explicitly takes precedence over the original. It does not resolve contradictory answers within itself."
                                    : "Confirm the official document order and precedence before mapping replacements. Unmapped findings remain separate."}
                                </span>
                              </div>
                            </aside>
                          )}
                        </div>
                      </>
                    )}
                    <p className="coverage-note">
                      <ShieldCheck size={14} />
                      {detail.mode === "reviewed_demo"
                        ? "Real public documents. Fictional company profile. Selected, reviewed requirements—not an exhaustive compliance review."
                        : "AI findings are unreviewed. Verify extracted conditions, document completeness, and submission deadlines."}
                    </p>
                  </>
                )
              )}
            </>
          )}
          {tab === "profile" && profile && (
            <>
              <div className="heading-row">
                <div>
                  <div className="eyebrow teal">
                    YOUR COMPANY / CAPABILITIES & EVIDENCE
                  </div>
                  <h1>A bid is only as strong as its evidence.</h1>
                  <p className="subtitle">
                    Tell BidLens what your team can do. Leave uncertain answers
                    unknown.
                  </p>
                </div>
                <button
                  className="button primary"
                  onClick={saveProfile}
                  disabled={busy}
                >
                  {busy ? (
                    <Loader2 className="spin" size={16} />
                  ) : (
                    <CheckCheck size={17} />
                  )}
                  Save & reassess
                </button>
              </div>
              <div className="profile-note">
                <Sparkles size={18} />
                <div>
                  <strong>Try the impact loop.</strong> Change “Problem
                  management module” to Yes and add evidence. Save, then return
                  to the bid review to see the blocker resolve.
                </div>
              </div>
              <section className="profile-card">
                <div className="profile-card-heading">
                  <div>
                    <label htmlFor="company-name">Company name</label>
                    <input
                      id="company-name"
                      value={profile.name}
                      maxLength={150}
                      onChange={(e) =>
                        setProfile({ ...profile, name: e.target.value })
                      }
                    />
                  </div>
                  <span className="pill">
                    Profile version {profile.version}
                  </span>
                </div>
                {profile.fields.map((field) => (
                  <div className="fact-row" key={field.key}>
                    <div>
                      <label htmlFor={`fact-${field.key}`}>{field.label}</label>
                      <span>
                        {field.type === "number"
                          ? "Planning context; not used as an eligibility threshold."
                          : "A source, document, or specific explanation supports the answer."}
                      </span>
                    </div>
                    {field.type === "number" ? (
                      <input
                        id={`fact-${field.key}`}
                        type="number"
                        min="0"
                        value={
                          profile.facts[field.key]?.value === null
                            ? ""
                            : Number(profile.facts[field.key]?.value || 0)
                        }
                        onChange={(e) =>
                          setProfile({
                            ...profile,
                            facts: {
                              ...profile.facts,
                              [field.key]: {
                                ...profile.facts[field.key],
                                value:
                                  e.target.value === ""
                                    ? null
                                    : Number(e.target.value),
                              },
                            },
                          })
                        }
                      />
                    ) : (
                      <select
                        id={`fact-${field.key}`}
                        value={
                          profile.facts[field.key]?.value === null
                            ? "unknown"
                            : String(
                                profile.facts[field.key]?.value ?? "unknown",
                              )
                        }
                        onChange={(e) =>
                          setProfile({
                            ...profile,
                            facts: {
                              ...profile.facts,
                              [field.key]: {
                                ...profile.facts[field.key],
                                value:
                                  e.target.value === "unknown"
                                    ? null
                                    : e.target.value === "true",
                              },
                            },
                          })
                        }
                      >
                        <option value="unknown">Unknown</option>
                        <option value="true">Yes</option>
                        <option value="false">No</option>
                      </select>
                    )}
                    <textarea
                      aria-label={`${field.label} supporting evidence`}
                      rows={2}
                      placeholder="Supporting evidence…"
                      value={profile.facts[field.key]?.evidence || ""}
                      onChange={(e) =>
                        setProfile({
                          ...profile,
                          facts: {
                            ...profile.facts,
                            [field.key]: {
                              ...profile.facts[field.key],
                              evidence: e.target.value,
                            },
                          },
                        })
                      }
                    />
                  </div>
                ))}
              </section>
            </>
          )}
          {tab === "sources" && (
            <>
              <div className="heading-row">
                <div>
                  <div className="eyebrow teal">
                    SOURCE LIBRARY / DOCUMENT PROVENANCE
                  </div>
                  <h1>Start with the source.</h1>
                  <p className="subtitle">
                    Original files, preserved page numbers, and a traceable
                    chain of evidence.
                  </p>
                </div>
                <span className="pill">
                  <Fingerprint size={14} />
                  SHA-256 verified
                </span>
              </div>
              <div className="source-grid">
                {detail?.documents.map((d) => (
                  <article className="document-card" key={d.id}>
                    <div className="document-top">
                      <div className="document-icon">
                        <FileText size={28} />
                      </div>
                      <span className="pill">{d.pages} pages</span>
                    </div>
                    <h3>{d.name}</h3>
                    <p>{detail.title}</p>
                    <span className="eyebrow">
                      {d.mode === "reviewed_demo"
                        ? "CURATED DEMO ANNOTATIONS"
                        : "AI EXTRACTED · UNREVIEWED"}
                    </span>
                    <div className="hash" title={d.sha256}>
                      <Fingerprint size={14} />
                      {d.sha256.slice(0, 24)}…
                    </div>
                    <div className="document-links">
                      {d.pdf_available && (
                        <a
                          className="button secondary"
                          href={`/api/documents/${d.id}/pdf`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          View PDF <ArrowUpRight size={14} />
                        </a>
                      )}
                      {d.url && (
                        <a href={d.url} target="_blank" rel="noreferrer">
                          Official original <ArrowUpRight size={14} />
                        </a>
                      )}
                    </div>
                  </article>
                ))}
              </div>
              <section className="import-card">
                <div className="import-heading">
                  <div className="guide-icon">
                    <Upload size={22} />
                  </div>
                  <div>
                    <h3>Bring another RFP into focus.</h3>
                    <p>
                      Extract cited requirements from a government PDF. Live
                      findings start as “needs confirmation.”
                    </p>
                  </div>
                  <span
                    className={`pill ${health?.live_extraction ? "enabled" : ""}`}
                  >
                    {health?.live_extraction
                      ? "Ready to import"
                      : "API key required"}
                  </span>
                </div>
                {!health?.live_extraction && (
                  <div className="setup-note">
                    The reviewed demo runs without a key. To import your own
                    document, set <code>OPENAI_API_KEY</code> and{" "}
                    <code>OPENAI_MODEL</code> in your local <code>.env</code>{" "}
                    and restart the API and worker.
                  </div>
                )}
                <form onSubmit={importPdf}>
                  <label className="import-target">
                    Add this document to
                    <select
                      value={importTarget}
                      onChange={(e) => {
                        setImportTarget(e.target.value);
                        const o = opportunities.find(
                          (x) => x.id === e.target.value,
                        );
                        if (o) {
                          setImportTitle(o.title);
                          setAgency(o.agency);
                        }
                      }}
                    >
                      <option value="">A new opportunity (original RFP)</option>
                      {opportunities
                        .filter((o) => o.mode !== "reviewed_demo")
                        .map((o) => (
                          <option key={o.id} value={o.id}>
                            Amendment to: {o.title}
                          </option>
                        ))}
                    </select>
                  </label>
                  <div className="form-grid">
                    <label>
                      Opportunity title
                      <input
                        required
                        minLength={3}
                        maxLength={200}
                        placeholder="e.g. Customer service platform"
                        value={importTitle}
                        onChange={(e) => setImportTitle(e.target.value)}
                      />
                    </label>
                    <label>
                      Government agency
                      <input
                        required
                        minLength={2}
                        maxLength={200}
                        placeholder="e.g. City of Ann Arbor"
                        value={agency}
                        onChange={(e) => setAgency(e.target.value)}
                      />
                    </label>
                  </div>
                  <label>
                    Official PDF URL
                    <input
                      type="url"
                      required={!upload}
                      placeholder="https://www.a2gov.org/…/document.pdf"
                      disabled={!!upload}
                      value={sourceUrl}
                      onChange={(e) => setSourceUrl(e.target.value)}
                    />
                  </label>
                  <div className="import-footer">
                    <label className="file-upload">
                      <Plus size={16} />
                      Or upload a PDF
                      <input
                        aria-label="Upload a PDF"
                        type="file"
                        accept="application/pdf,.pdf"
                        onChange={(e) => setUpload(e.target.files?.[0] || null)}
                      />
                    </label>
                    {upload && (
                      <span className="uploaded-name">
                        {upload.name}
                        <button
                          type="button"
                          onClick={() => setUpload(null)}
                          aria-label="Remove upload"
                        >
                          <X size={13} />
                        </button>
                      </span>
                    )}
                    <span className="small">20 MB · 150 pages max</span>
                    <button
                      className="button primary"
                      type="submit"
                      disabled={!health?.live_extraction || busy}
                    >
                      {busy ? (
                        <Loader2 size={16} className="spin" />
                      ) : (
                        <Upload size={16} />
                      )}
                      Extract requirements
                    </button>
                  </div>
                </form>
                <p className="small">
                  Imported findings require a person to verify capability
                  mappings and amendment precedence. Upload originals first,
                  then amendments in official order. PDF text is sent to the
                  configured OpenAI model.
                </p>
              </section>
              {jobs.length > 0 && (
                <section className="jobs">
                  <h3>Processing queue</h3>
                  {jobs.map((j) => (
                    <div className="job-row" key={j.id}>
                      <span className={`pill ${j.status}`}>{j.status}</span>
                      <code>{j.id.slice(0, 8)}</code>
                      <span>{j.error || `Attempt ${j.attempts} of 3`}</span>
                      {j.status === "completed" && (
                        <button
                          className="text-button"
                          onClick={() => {
                            setSelected(j.opportunity_id);
                            setStage(undefined);
                            setTab("qualify");
                          }}
                        >
                          Open review <ArrowRight size={14} />
                        </button>
                      )}
                      {j.status === "failed" && (
                        <button
                          className="text-button"
                          onClick={async () => {
                            try {
                              await api(`/jobs/${j.id}/dismiss`, {
                                method: "POST",
                              });
                              setJobs(await api<Job[]>("/jobs"));
                            } catch (e) {
                              setError((e as Error).message);
                            }
                          }}
                        >
                          Dismiss
                        </button>
                      )}
                      {j.status === "failed" && j.attempts < 3 && (
                        <button
                          className="text-button"
                          onClick={async () => {
                            try {
                              await api(`/jobs/${j.id}/retry`, {
                                method: "POST",
                              });
                              setJobs(await api<Job[]>("/jobs"));
                            } catch (e) {
                              setError((e as Error).message);
                            }
                          }}
                        >
                          Retry
                        </button>
                      )}
                    </div>
                  ))}
                </section>
              )}
            </>
          )}
          {tab === "activity" && (
            <>
              <div className="eyebrow teal">
                REVIEW HISTORY / APPEND-ONLY EVENTS
              </div>
              <h1>Every decision has a trail.</h1>
              <p className="subtitle">
                Profile changes and corrections stay visible. A correction
                applies only to the requirement version reviewed.
              </p>
              <div className="audit-list">
                {audit.length === 0 ? (
                  <div className="empty">
                    <History size={26} />
                    <h3>Your review history starts here.</h3>
                    <p>
                      Save a company profile or correct a requirement to create
                      the first event.
                    </p>
                  </div>
                ) : (
                  audit.map((a) => (
                    <article className="audit-row" key={a.id}>
                      <span className="audit-dot" />
                      <div>
                        <h3>{a.action.replaceAll("_", " ")}</h3>
                        <p>{new Date(a.created_at * 1000).toLocaleString()}</p>
                        <dl>
                          {Object.entries(a.detail).map(([k, v]) => (
                            <div key={k}>
                              <dt>{k.replaceAll("_", " ")}</dt>
                              <dd>
                                {Array.isArray(v) ? v.join(", ") : String(v)}
                              </dd>
                            </div>
                          ))}
                        </dl>
                      </div>
                    </article>
                  ))
                )}
              </div>
            </>
          )}
        </main>
        <footer>
          <span>
            BidLens <span className="footer-dot">/</span> Better bids begin with
            better questions.
          </span>
          <span>Built on public government data.</span>
        </footer>
      </div>
      <dialog
        ref={dialog}
        onCancel={() => setCorrection(null)}
        onClick={(e) => {
          if (e.target === dialog.current) setCorrection(null);
        }}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            saveCorrection();
          }}
        >
          <div className="dialog-heading">
            <h2>Review classification</h2>
            <button
              type="button"
              className="icon-button"
              onClick={() => setCorrection(null)}
              aria-label="Close review"
            >
              <X size={19} />
            </button>
          </div>
          <p>{correction?.title}</p>
          <div className="setup-note">
            This changes only this requirement version. It preserves the source
            and does not resolve a source conflict.
          </div>
          <label>
            Classification
            <select
              value={importance}
              onChange={(e) => setImportance(e.target.value)}
            >
              <option value="mandatory">Mandatory</option>
              <option value="preferred">Preferred</option>
              <option value="informational">Informational</option>
            </select>
          </label>
          <label>
            Reason for correction
            <textarea
              required
              minLength={10}
              maxLength={2000}
              rows={4}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Explain the interpretation and supporting source…"
            />
          </label>
          <div className="dialog-actions">
            <button
              type="button"
              className="button secondary"
              onClick={() => setCorrection(null)}
            >
              Cancel
            </button>
            <button
              className="button primary"
              disabled={busy || reason.trim().length < 10}
            >
              Save correction
            </button>
          </div>
        </form>
      </dialog>
      <dialog ref={mappingDialog} onCancel={() => setMapping(null)}>
        <form onSubmit={saveMapping}>
          <div className="dialog-heading">
            <h2>Verify requirement mapping</h2>
            <button
              type="button"
              className="icon-button"
              onClick={() => setMapping(null)}
              aria-label="Close mapping"
            >
              <X size={18} />
            </button>
          </div>
          <p>{mapping?.title}</p>
          <div className="setup-note">
            Read the citation first. Only choose a capability if it fully
            represents this requirement, including its conditions. Otherwise
            leave it for manual review.
          </div>
          <label>
            Compare to company capability
            <select
              value={mapField}
              onChange={(e) => setMapField(e.target.value)}
            >
              <option value="">Manual review — no automatic rule</option>
              {mappingOptions.fields.map((f) => (
                <option key={f.key} value={f.key}>
                  {f.label}
                </option>
              ))}
            </select>
          </label>
          {mappingOptions.previous.length > 0 && (
            <label>
              This amendment explicitly replaces
              <select
                value={mapPrevious}
                onChange={(e) => setMapPrevious(e.target.value)}
              >
                <option value="">Nothing — keep as a separate finding</option>
                {mappingOptions.previous.map((r) => (
                  <option key={r.key} value={r.key}>
                    {r.title}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={mapConflict}
              onChange={(e) => setMapConflict(e.target.checked)}
            />
            The source contains conflicting or unresolved wording
          </label>
          <label>
            Reason and source interpretation
            <textarea
              required
              minLength={10}
              maxLength={2000}
              rows={3}
              value={mapReason}
              onChange={(e) => setMapReason(e.target.value)}
              placeholder="Explain why this comparison and replacement are supported…"
            />
          </label>
          <div className="dialog-actions">
            <button
              type="button"
              className="button secondary"
              onClick={() => setMapping(null)}
            >
              Cancel
            </button>
            <button
              className="button primary"
              disabled={busy || mapReason.trim().length < 10}
            >
              Verify & reassess
            </button>
          </div>
        </form>
      </dialog>
    </div>
  );
  function EvidencePanel() {
    return (
      <aside className="evidence-panel">
        <div className="evidence-header">
          <div>
            <span className="eyebrow teal">SOURCE EVIDENCE</span>
            <h3>
              {page?.name || "Loading source…"}{" "}
              <span>p. {evidence?.cite.page}</span>
            </h3>
          </div>
          <button
            className="icon-button"
            onClick={() => setEvidence(null)}
            aria-label="Close evidence"
          >
            <X size={18} />
          </button>
        </div>
        {evidence && (
          <>
            <div className="evidence-context">{evidence.requirement.title}</div>
            <blockquote>{evidence.cite.quote}</blockquote>
            <div className="evidence-tabs">
              <button
                className={!pdfView ? "selected" : ""}
                onClick={() => setPdfView(false)}
              >
                Page text
              </button>
              <button
                className={pdfView ? "selected" : ""}
                disabled={!page?.pdf_available}
                onClick={() => setPdfView(true)}
              >
                Original PDF
              </button>
              {page?.url && (
                <a
                  href={`${page.url}#page=${evidence.cite.page}`}
                  target="_blank"
                  rel="noreferrer"
                  aria-label="Open official source"
                >
                  <ArrowUpRight size={15} />
                </a>
              )}
            </div>
            {!page ? (
              <div className="loading">
                <Loader2 className="spin" size={18} />
              </div>
            ) : pdfView ? (
              <iframe
                title={`Source PDF page ${evidence.cite.page}`}
                src={`/api/documents/${evidence.cite.document_id}/pdf#page=${evidence.cite.page}`}
                className="pdf-frame"
              />
            ) : (
              <Highlight text={page.text} quote={evidence.cite.quote} />
            )}
            <div className="evidence-footer">
              <Fingerprint size={14} />
              Quote verified against preserved page text.
            </div>
            {Object.keys(evidence.requirement.company_evidence).length > 0 && (
              <div className="company-evidence">
                <span className="eyebrow">COMPANY EVIDENCE</span>
                {Object.entries(evidence.requirement.company_evidence).map(
                  ([key, fact]) => (
                    <p key={key}>
                      <strong>
                        {key.replaceAll("_", " ")}:{" "}
                        {String(fact?.value ?? "unknown")}
                      </strong>
                      {fact?.evidence || "No evidence recorded."}
                    </p>
                  ),
                )}
              </div>
            )}
          </>
        )}
      </aside>
    );
  }
}
