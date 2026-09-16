"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Zap, GitFork, MessageSquare, Network, GitBranch,
  BarChart3, ArrowLeft, Loader2, AlertCircle, RefreshCw, ExternalLink
} from "lucide-react";
import { api, getAccessToken, type Repository, type JobStatus } from "@/lib/api";
import ChatTab from "./tabs/ChatTab";
import ArchitectureTab from "./tabs/ArchitectureTab";
import TraceTab from "./tabs/TraceTab";
import HealthTab from "./tabs/HealthTab";

type Tab = "chat" | "architecture" | "trace" | "health";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "chat",         label: "Chat",         icon: MessageSquare },
  { id: "architecture", label: "Architecture", icon: Network },
  { id: "trace",        label: "Trace",        icon: GitBranch },
  { id: "health",       label: "Health Report",icon: BarChart3 },
];

// ── Progress display during indexing ─────────────────────────────────────────

const STAGE_LABELS: Record<string, string> = {
  pending:            "Queued",
  cloning:            "Cloning repository…",
  detecting_language: "Detecting languages…",
  parsing:            "Parsing source files…",
  building_graph:     "Building knowledge graph…",
  embedding:          "Generating embeddings…",
  static_analysis:    "Running static analysis…",
  report_generation:  "Computing health score…",
  done:               "Indexing complete!",
  failed:             "Indexing failed",
};

function IndexingProgress({ jobId, onComplete }: { jobId: string | null; onComplete: () => void }) {
  const [job, setJob] = useState<JobStatus | null>(null);

  useEffect(() => {
    if (!jobId) return;
    const poll = async () => {
      try {
        const status = await api.jobs.status(jobId);
        setJob(status);
        if (status.stage === "done") {
          onComplete();
          return;
        }
        if (status.stage !== "failed") {
          setTimeout(poll, 3000);
        }
      } catch {}
    };
    poll();
  }, [jobId, onComplete]);

  if (!job) return null;

  const label = STAGE_LABELS[job.stage] || job.stage;

  return (
    <div style={{ padding: "40px 0", textAlign: "center" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <div style={{ marginBottom: 20 }}>
          {job.stage === "failed" ? (
            <AlertCircle size={40} color="var(--danger)" style={{ margin: "0 auto 12px" }} />
          ) : (
            <Loader2 size={40} color="var(--primary)" className="animate-spin" style={{ margin: "0 auto 12px" }} />
          )}
          <h3 style={{ fontSize: "1.1rem", marginBottom: 6 }}>{label}</h3>
          {job.error_message && (
            <p style={{ color: "var(--danger)", fontSize: "0.875rem" }}>{job.error_message}</p>
          )}
        </div>
        <div className="progress-bar" style={{ maxWidth: 360, margin: "0 auto" }}>
          <div className="progress-fill" style={{ width: `${job.progress_pct}%` }} />
        </div>
        <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: 10 }}>
          {job.progress_pct}% complete
        </p>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function RepoDetailPage() {
  const params = useParams();
  const router = useRouter();
  const repoId = params.id as string;

  const [repo, setRepo] = useState<Repository | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const [loading, setLoading] = useState(true);
  const [jobId, setJobId] = useState<string | null>(null);

  useEffect(() => {
    if (!getAccessToken()) { router.replace("/"); return; }
    loadRepo();
  }, [repoId]);

  const loadRepo = async () => {
    try {
      const data = await api.repos.get(repoId);
      setRepo(data);
      setLoading(false);
    } catch {
      router.replace("/dashboard");
    }
  };

  const handleIndexingComplete = () => {
    setJobId(null);
    loadRepo();
  };

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Loader2 size={32} color="var(--primary)" className="animate-spin" />
      </div>
    );
  }

  if (!repo) return null;

  const isIndexing = repo.status === "indexing" || repo.status === "pending";
  const isFailed = repo.status === "failed";
  const isReady = repo.status === "ready";

  return (
    <div className="page-layout">
      {/* Nav */}
      <nav className="nav">
        <div className="container" style={{ display: "flex", alignItems: "center", gap: 16, height: 64 }}>
          <Link href="/dashboard" style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-secondary)", textDecoration: "none", fontSize: "0.875rem", transition: "color 0.2s" }}>
            <ArrowLeft size={16} /> Dashboard
          </Link>
          <div style={{ width: 1, height: 20, background: "var(--border)" }} />
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <GitFork size={15} color="var(--text-muted)" />
            <a
              href={repo.source_url}
              target="_blank"
              rel="noopener"
              style={{ fontFamily: "var(--font-mono)", fontSize: "0.875rem", color: "var(--text-primary)", textDecoration: "none", display: "flex", alignItems: "center", gap: 5 }}
            >
              {repo.full_name}
              <ExternalLink size={11} color="var(--text-muted)" />
            </a>
          </div>
          {repo.primary_language && (
            <span className="badge badge-muted" style={{ marginLeft: "auto" }}>
              {repo.primary_language}
            </span>
          )}
          {repo.health_score !== null && (
            <span style={{
              fontWeight: 800, fontSize: "1.1rem",
              color: repo.health_score >= 80 ? "var(--success)" : repo.health_score >= 60 ? "#84cc16" : repo.health_score >= 40 ? "var(--warning)" : "var(--danger)"
            }}>
              {repo.health_score}
              <span style={{ fontSize: "0.7rem", fontWeight: 500, color: "var(--text-muted)", marginLeft: 3 }}>/ 100</span>
            </span>
          )}
        </div>
      </nav>

      {/* Status: indexing */}
      {(isIndexing || isFailed) && (
        <div className="container" style={{ paddingTop: 32 }}>
          <div className="glass-card" style={{ padding: 32 }}>
            {isIndexing ? (
              <IndexingProgress jobId={jobId} onComplete={handleIndexingComplete} />
            ) : (
              <div style={{ textAlign: "center", padding: "32px 0" }}>
                <AlertCircle size={40} color="var(--danger)" style={{ margin: "0 auto 16px" }} />
                <h3 style={{ marginBottom: 12 }}>Indexing failed</h3>
                <p style={{ color: "var(--text-secondary)", marginBottom: 20, fontSize: "0.9rem" }}>
                  There was an error processing this repository.
                </p>
                <button className="btn-primary" onClick={async () => {
                  const res = await api.repos.reindex(repoId);
                  setJobId(res.job_id);
                  setRepo((r) => r ? { ...r, status: "indexing" } : r);
                }}>
                  <RefreshCw size={15} /> Retry indexing
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tabs (only when ready) */}
      {isReady && (
        <>
          {/* Tab bar */}
          <div style={{ borderBottom: "1px solid var(--border)", background: "rgba(5,9,18,0.7)", backdropFilter: "blur(12px)", position: "sticky", top: 64, zIndex: 40 }}>
            <div className="container" style={{ display: "flex", gap: 0 }}>
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  id={`tab-${tab.id}`}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    display: "flex", alignItems: "center", gap: 8,
                    padding: "14px 20px",
                    fontSize: "0.875rem",
                    fontWeight: 600,
                    color: activeTab === tab.id ? "var(--primary-light)" : "var(--text-muted)",
                    background: "none",
                    border: "none",
                    borderBottom: activeTab === tab.id ? "2px solid var(--primary)" : "2px solid transparent",
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                    marginBottom: -1,
                  }}
                >
                  <tab.icon size={15} />
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Tab content */}
          <div className="container" style={{ padding: "32px 24px", flex: 1 }}>
            {activeTab === "chat" && <ChatTab repoId={repoId} />}
            {activeTab === "architecture" && <ArchitectureTab repoId={repoId} />}
            {activeTab === "trace" && <TraceTab repoId={repoId} />}
            {activeTab === "health" && <HealthTab repoId={repoId} />}
          </div>
        </>
      )}
    </div>
  );
}
