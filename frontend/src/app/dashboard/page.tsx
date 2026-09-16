"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Plus, GitFork, Zap, BarChart3, Clock, Code2, Trash2,
  RefreshCw, ArrowRight, LogOut, AlertCircle, CheckCircle,
  Loader2, X, ExternalLink
} from "lucide-react";
import { api, getAccessToken, clearTokens, type Repository } from "@/lib/api";

// ── Import form modal ─────────────────────────────────────────────────────────

function ImportModal({ onClose, onImported }: { onClose: () => void; onImported: (repo: { repository_id: string; job_id: string }) => void }) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true);
    setError("");
    try {
      const result = await api.repos.import(url.trim());
      onImported(result);
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to import repository");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 100,
        background: "rgba(5, 9, 18, 0.85)",
        backdropFilter: "blur(8px)",
        display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="glass-card animate-fade-in-up" style={{ width: "100%", maxWidth: 520, padding: 36 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
          <div>
            <h2 style={{ fontSize: "1.3rem", marginBottom: 6 }}>Import Repository</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
              Paste a public GitHub URL to start indexing
            </p>
          </div>
          <button onClick={onClose} className="btn-ghost" style={{ padding: "6px 10px", minWidth: "auto" }}>
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", fontSize: "0.875rem", fontWeight: 600, marginBottom: 8, color: "var(--text-secondary)" }}>
              GitHub Repository URL
            </label>
            <input
              className="input"
              type="url"
              placeholder="https://github.com/owner/repository"
              value={url}
              onChange={(e) => { setUrl(e.target.value); setError(""); }}
              autoFocus
              style={{ fontFamily: "var(--font-mono)", fontSize: "0.875rem" }}
            />
          </div>

          {error && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: 8, marginBottom: 16, color: "#f87171", fontSize: "0.875rem" }}>
              <AlertCircle size={14} /> {error}
            </div>
          )}

          <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
            <button type="button" onClick={onClose} className="btn-ghost" style={{ flex: 1 }}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={loading || !url.trim()} style={{ flex: 2 }}>
              {loading ? <><Loader2 size={15} className="animate-spin" /> Importing…</> : <><GitFork size={15} /> Import Repository</>}
            </button>
          </div>
        </form>

        <p style={{ marginTop: 20, fontSize: "0.8rem", color: "var(--text-muted)", textAlign: "center" }}>
          V1 supports public GitHub repos up to 50,000 LOC
        </p>
      </div>
    </div>
  );
}

// ── Repository card ───────────────────────────────────────────────────────────

function scoreColor(score: number | null) {
  if (score === null) return "var(--text-muted)";
  if (score >= 80) return "var(--success)";
  if (score >= 60) return "#84cc16";
  if (score >= 40) return "var(--warning)";
  return "var(--danger)";
}

function StatusBadge({ status }: { status: Repository["status"] }) {
  const map = {
    pending:  { label: "Pending",  cls: "badge-muted" },
    indexing: { label: "Indexing", cls: "badge-primary" },
    ready:    { label: "Ready",    cls: "badge-success" },
    failed:   { label: "Failed",   cls: "badge-danger" },
  };
  const { label, cls } = map[status] || map.pending;
  return (
    <span className={`badge ${cls}`}>
      {status === "indexing" && <Loader2 size={10} className="animate-spin" />}
      {status === "ready" && <CheckCircle size={10} />}
      {status === "failed" && <AlertCircle size={10} />}
      {label}
    </span>
  );
}

function LangBadge({ lang }: { lang: string | null }) {
  if (!lang) return null;
  const colors: Record<string, string> = {
    Python: "#3776ab", JavaScript: "#f7df1e", TypeScript: "#3178c6",
    Java: "#ed8b00", Go: "#00add8", Ruby: "#cc342d", Rust: "#dea584",
  };
  const bg = colors[lang] || "var(--primary)";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: "0.75rem", color: "var(--text-secondary)" }}>
      <span style={{ width: 9, height: 9, borderRadius: "50%", background: bg, display: "inline-block" }} />
      {lang}
    </span>
  );
}

function RepoCard({ repo, onDelete, onReindex }: { repo: Repository; onDelete: (id: string) => void; onReindex: (id: string) => void }) {
  const [deleting, setDeleting] = useState(false);
  const [reindexing, setReindexing] = useState(false);

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (!confirm(`Delete ${repo.full_name} and all derived data?`)) return;
    setDeleting(true);
    try {
      await api.repos.delete(repo.id);
      onDelete(repo.id);
    } catch {}
    setDeleting(false);
  };

  const handleReindex = async (e: React.MouseEvent) => {
    e.preventDefault();
    setReindexing(true);
    try {
      await api.repos.reindex(repo.id);
      onReindex(repo.id);
    } catch {}
    setReindexing(false);
  };

  const timeAgo = repo.last_indexed_at
    ? new Date(repo.last_indexed_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
    : null;

  return (
    <Link
      href={repo.status === "ready" ? `/repos/${repo.id}` : "#"}
      style={{ textDecoration: "none", display: "block" }}
    >
      <div
        className="glass-card"
        style={{
          padding: 24,
          cursor: repo.status === "ready" ? "pointer" : "default",
          transition: "all 0.25s ease",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <GitFork size={16} color="var(--text-muted)" />
              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                {repo.full_name}
              </span>
            </div>
            <h3 style={{ fontSize: "1.05rem", marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {repo.name}
            </h3>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <LangBadge lang={repo.primary_language} />
              <StatusBadge status={repo.status} />
            </div>
          </div>

          {/* Health score */}
          <div style={{ textAlign: "right", marginLeft: 16, flexShrink: 0 }}>
            <div style={{ fontSize: "2rem", fontWeight: 900, color: scoreColor(repo.health_score), lineHeight: 1 }}>
              {repo.health_score !== null ? repo.health_score : "—"}
            </div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: 2 }}>health</div>
          </div>
        </div>

        {/* Footer */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--border)", paddingTop: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.8rem", color: "var(--text-muted)" }}>
            <Clock size={12} />
            {timeAgo ? `Indexed ${timeAgo}` : "Not yet indexed"}
          </div>

          <div style={{ display: "flex", gap: 6 }} onClick={(e) => e.preventDefault()}>
            {repo.status === "ready" && (
              <button
                onClick={handleReindex}
                className="btn-ghost"
                disabled={reindexing}
                style={{ padding: "5px 10px", fontSize: "0.8rem", gap: 5 }}
                title="Re-index"
              >
                <RefreshCw size={13} className={reindexing ? "animate-spin" : ""} />
              </button>
            )}
            <button
              onClick={handleDelete}
              className="btn-ghost"
              disabled={deleting}
              style={{ padding: "5px 10px", fontSize: "0.8rem", color: "var(--danger)", borderColor: "rgba(239,68,68,0.2)" }}
              title="Delete"
            >
              {deleting ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
            </button>
          </div>
        </div>
      </div>
    </Link>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({ onImport }: { onImport: () => void }) {
  return (
    <div
      className="glass-card animate-fade-in-up"
      style={{ padding: "64px 32px", textAlign: "center", maxWidth: 480, margin: "0 auto" }}
    >
      <div style={{ width: 72, height: 72, borderRadius: 18, background: "linear-gradient(135deg, var(--primary-glow), transparent)", border: "1px solid var(--border-hover)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 24px" }}>
        <Code2 size={32} color="var(--primary-light)" />
      </div>
      <h3 style={{ fontSize: "1.3rem", marginBottom: 12 }}>No repositories yet</h3>
      <p style={{ color: "var(--text-secondary)", lineHeight: 1.7, marginBottom: 28, fontSize: "0.95rem" }}>
        Paste a public GitHub URL to get started. DevLens will build an Engineering Knowledge Graph and give you AI-powered insights within 15 minutes.
      </p>
      <button className="btn-primary" onClick={onImport} style={{ margin: "0 auto" }}>
        <Plus size={16} /> Import your first repository
      </button>
    </div>
  );
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const router = useRouter();
  const [repos, setRepos] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [showImport, setShowImport] = useState(false);
  const [username, setUsername] = useState("");

  // Auth guard
  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/");
      return;
    }
    const stored = sessionStorage.getItem("devlens_user");
    if (stored) {
      try { setUsername(JSON.parse(stored).username); } catch {}
    }
  }, [router]);

  // Load repos
  const loadRepos = useCallback(async () => {
    try {
      const data = await api.repos.list();
      setRepos(data.repositories);
    } catch {
      // If 401, the API client handles redirect
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadRepos(); }, [loadRepos]);

  // Poll indexing repos
  useEffect(() => {
    const indexing = repos.filter((r) => r.status === "indexing" || r.status === "pending");
    if (indexing.length === 0) return;
    const timer = setTimeout(loadRepos, 5000);
    return () => clearTimeout(timer);
  }, [repos, loadRepos]);

  const handleImported = (_result: { repository_id: string; job_id: string }) => {
    loadRepos();
  };

  const handleDelete = (id: string) => {
    setRepos((prev) => prev.filter((r) => r.id !== id));
  };

  const handleReindex = (id: string) => {
    setRepos((prev) => prev.map((r) => r.id === id ? { ...r, status: "pending" } : r));
    loadRepos();
  };

  const handleLogout = () => {
    clearTokens();
    sessionStorage.removeItem("devlens_user");
    router.replace("/");
  };

  return (
    <div className="page-layout">
      {/* Nav */}
      <nav className="nav">
        <div className="container" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", height: 64 }}>
          <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none", color: "inherit" }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: "linear-gradient(135deg, var(--primary), var(--accent))", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Zap size={18} color="white" />
            </div>
            <span style={{ fontWeight: 800, fontSize: "1.05rem", letterSpacing: "-0.03em" }}>
              Dev<span className="gradient-text">Lens</span>
            </span>
          </Link>

          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {username && (
              <span style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                @{username}
              </span>
            )}
            <button onClick={handleLogout} className="btn-ghost" style={{ padding: "8px 14px", gap: 6, fontSize: "0.875rem" }}>
              <LogOut size={15} /> Sign out
            </button>
          </div>
        </div>
      </nav>

      {/* Content */}
      <main className="container" style={{ padding: "48px 24px", flex: 1 }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 40, flexWrap: "wrap", gap: 16 }}>
          <div>
            <h1 style={{ fontSize: "2rem", fontWeight: 800, marginBottom: 6, letterSpacing: "-0.03em" }}>
              Repositories
            </h1>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
              {repos.length > 0
                ? `${repos.length} repositor${repos.length === 1 ? "y" : "ies"} · ${repos.filter((r) => r.status === "ready").length} ready`
                : "Import a GitHub repository to get started"}
            </p>
          </div>
          <button className="btn-primary" onClick={() => setShowImport(true)}>
            <Plus size={16} /> Import Repository
          </button>
        </div>

        {/* Repos grid */}
        {loading ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
              gap: 16,
            }}
          >
            {[...Array(3)].map((_, i) => (
              <div key={i} className="glass-card" style={{ padding: 24, height: 160 }}>
                <div className="skeleton" style={{ height: 20, width: "60%", marginBottom: 12 }} />
                <div className="skeleton" style={{ height: 14, width: "40%", marginBottom: 24 }} />
                <div className="skeleton" style={{ height: 14, width: "80%" }} />
              </div>
            ))}
          </div>
        ) : repos.length === 0 ? (
          <EmptyState onImport={() => setShowImport(true)} />
        ) : (
          <div
            className="stagger"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
              gap: 16,
            }}
          >
            {repos.map((repo) => (
              <RepoCard
                key={repo.id}
                repo={repo}
                onDelete={handleDelete}
                onReindex={handleReindex}
              />
            ))}
          </div>
        )}
      </main>

      {/* Import modal */}
      {showImport && (
        <ImportModal
          onClose={() => setShowImport(false)}
          onImported={handleImported}
        />
      )}
    </div>
  );
}
