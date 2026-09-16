"use client";

import { useState } from "react";
import { api, type TraceResult, type TraceStep } from "@/lib/api";
import { GitBranch, Send, Loader2, AlertCircle, CheckCircle, ArrowDown, Code2 } from "lucide-react";

const ROLE_COLORS: Record<string, string> = {
  entry_point:    "var(--primary)",
  handler:        "var(--accent)",
  business_logic: "#a78bfa",
  data_access:    "var(--success)",
  utility:        "var(--warning)",
};

const ROLE_LABELS: Record<string, string> = {
  entry_point:    "Entry Point",
  handler:        "Handler",
  business_logic: "Business Logic",
  data_access:    "Data Access",
  utility:        "Utility",
};

function StepCard({ step, isLast }: { step: TraceStep; isLast: boolean }) {
  const color = ROLE_COLORS[step.role] || "var(--primary)";
  const label = ROLE_LABELS[step.role] || step.role;
  const filename = step.file_path.split("/").pop() ?? step.file_path;

  return (
    <div style={{ position: "relative" }}>
      <div
        className="glass-card"
        style={{ padding: 20, display: "flex", gap: 16, alignItems: "flex-start" }}
      >
        {/* Step number */}
        <div style={{
          width: 36,
          height: 36,
          borderRadius: 10,
          background: `${color}20`,
          border: `1px solid ${color}40`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          fontWeight: 800,
          fontSize: "0.9rem",
          color,
        }}>
          {step.order}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>{step.name}</span>
            <span className="badge" style={{ background: `${color}15`, color, border: `1px solid ${color}30`, fontSize: "0.72rem" }}>
              {label}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-muted)", fontSize: "0.8rem", fontFamily: "var(--font-mono)" }}>
            <Code2 size={12} />
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {step.file_path}
            </span>
          </div>
        </div>
      </div>

      {/* Connector arrow */}
      {!isLast && (
        <div style={{ display: "flex", justifyContent: "center", padding: "6px 0" }}>
          <ArrowDown size={18} color="var(--border-hover)" />
        </div>
      )}
    </div>
  );
}

const EXAMPLE_TRACES = [
  "login flow",
  "user registration",
  "API request handling",
  "database query",
  "authentication middleware",
];

export default function TraceTab({ repoId }: { repoId: string }) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TraceResult | null>(null);
  const [error, setError] = useState("");

  const handleTrace = async (description: string) => {
    if (!description.trim() || loading) return;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await api.trace.run(repoId, description);
      setResult(res);
    } catch (err: any) {
      setError(err.message || "Failed to trace feature");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: 8 }}>Feature Tracing</h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          Describe a feature in natural language. DevLens will identify the entry point and trace the path through the codebase using graph traversal.
        </p>
      </div>

      {/* Input */}
      <div className="glass-card" style={{ padding: 24, marginBottom: 28 }}>
        <div style={{ display: "flex", gap: 12 }}>
          <input
            className="input"
            placeholder='e.g. "login flow" or "how are API requests handled?"'
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleTrace(query)}
            style={{ flex: 1 }}
          />
          <button
            className="btn-primary"
            onClick={() => handleTrace(query)}
            disabled={loading || !query.trim()}
            id="trace-submit-btn"
            style={{ flexShrink: 0 }}
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            Trace
          </button>
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 14 }}>
          <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>Examples:</span>
          {EXAMPLE_TRACES.map((ex) => (
            <button
              key={ex}
              className="btn-ghost"
              style={{ fontSize: "0.78rem", padding: "4px 10px" }}
              onClick={() => { setQuery(ex); handleTrace(ex); }}
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ textAlign: "center", padding: "40px 0" }}>
          <Loader2 size={36} color="var(--primary)" className="animate-spin" style={{ margin: "0 auto 14px" }} />
          <p style={{ color: "var(--text-secondary)" }}>Tracing through the knowledge graph…</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="glass-card" style={{ padding: 20, color: "var(--danger)", display: "flex", alignItems: "center", gap: 10 }}>
          <AlertCircle size={18} /> {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="animate-fade-in">
          {/* Confidence header */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <CheckCircle size={18} color="var(--success)" />
              <span style={{ fontWeight: 600 }}>Trace complete: {result.steps.length} steps found</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>{result.confidence}</span>
              <div style={{ width: 80, height: 6, background: "var(--bg-elevated)", borderRadius: 3, overflow: "hidden" }}>
                <div style={{ width: `${result.completeness_pct}%`, height: "100%", background: "linear-gradient(90deg, var(--success), #84cc16)", borderRadius: 3 }} />
              </div>
              <span style={{ fontSize: "0.85rem", color: "var(--success)", fontWeight: 600 }}>{result.completeness_pct}%</span>
            </div>
          </div>

          {/* Steps */}
          <div style={{ maxWidth: 640 }}>
            {result.steps.map((step, i) => (
              <StepCard key={step.node_id} step={step} isLast={i === result.steps.length - 1} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
