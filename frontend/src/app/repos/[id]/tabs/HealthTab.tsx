"use client";

import { useEffect, useState } from "react";
import { api, type HealthReport } from "@/lib/api";
import { Loader2, AlertCircle, Shield, Zap, Copy, Clock, AlertTriangle } from "lucide-react";

// ── Score gauge ───────────────────────────────────────────────────────────────

function ScoreGauge({ score, label, size = 80 }: { score: number; label: string; size?: number }) {
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const color =
    score >= 80 ? "var(--success)" :
    score >= 60 ? "#84cc16" :
    score >= 40 ? "var(--warning)" :
    "var(--danger)";

  return (
    <div style={{ textAlign: "center" }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        {/* Background ring */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="var(--bg-elevated)" strokeWidth={8}
        />
        {/* Score ring */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 1s ease" }}
        />
      </svg>
      <div style={{ marginTop: -size / 2 - 4, fontSize: size > 60 ? "1.2rem" : "1rem", fontWeight: 800, color }}>
        {score}
      </div>
      <div style={{ marginTop: size / 2 - 8, fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 500 }}>{label}</div>
    </div>
  );
}

// ── Severity badge ────────────────────────────────────────────────────────────

const SEVERITY_MAP: Record<string, { cls: string; label: string }> = {
  critical: { cls: "badge-danger",  label: "Critical" },
  high:     { cls: "badge-danger",  label: "High" },
  medium:   { cls: "badge-warning", label: "Medium" },
  low:      { cls: "badge-muted",   label: "Low" },
  info:     { cls: "badge-primary", label: "Info" },
};

export default function HealthTab({ repoId }: { repoId: string }) {
  const [report, setReport] = useState<HealthReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api.health.get(repoId);
        setReport(data);
      } catch (err: any) {
        setError(err.message || "Health report not available");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [repoId]);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 400 }}>
        <Loader2 size={36} color="var(--primary)" className="animate-spin" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="glass-card" style={{ padding: 32, textAlign: "center", color: "var(--danger)" }}>
        <AlertCircle size={32} style={{ margin: "0 auto 12px" }} />
        <p>{error || "No health report available"}</p>
      </div>
    );
  }

  const scoreColor =
    report.overall_score >= 80 ? "var(--success)" :
    report.overall_score >= 60 ? "#84cc16" :
    report.overall_score >= 40 ? "var(--warning)" :
    "var(--danger)";

  const generatedAt = new Date(report.generated_at).toLocaleDateString("en-US", {
    month: "long", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit"
  });

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 32, flexWrap: "wrap", gap: 16 }}>
        <div>
          <h2 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: 6 }}>Repository Health Report</h2>
          <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-muted)", fontSize: "0.82rem" }}>
            <Clock size={13} /> Generated {generatedAt}
          </div>
        </div>
        {/* Overall score big display */}
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "4rem", fontWeight: 900, color: scoreColor, lineHeight: 1 }}>
            {report.overall_score}
          </div>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 2 }}>Overall Score / 100</div>
        </div>
      </div>

      {/* Score breakdown */}
      <div className="glass-card" style={{ padding: 28, marginBottom: 24 }}>
        <h3 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: 24, color: "var(--text-secondary)" }}>
          Score Breakdown
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 24 }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
            <ScoreGauge score={report.complexity_score} label="Complexity" size={88} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
            <ScoreGauge score={report.security_score} label="Security" size={88} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
            <ScoreGauge score={report.duplication_score} label="Duplication" size={88} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
            <ScoreGauge score={report.dependency_score} label="Dependencies" size={88} />
          </div>
        </div>
      </div>

      {/* Formula transparency box */}
      <div className="glass-card" style={{ padding: 20, marginBottom: 24, borderLeft: "3px solid var(--primary)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, fontSize: "0.85rem", fontWeight: 600, color: "var(--primary-light)" }}>
          <Zap size={14} /> Transparent scoring formula
        </div>
        <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", lineHeight: 1.7 }}>
          HealthScore = 100 − ComplexityPenalty(max 25) − SecurityPenalty(max 30) − DuplicationPenalty(max 20) − DependencyPenalty(max 15).
          Every point deducted is traceable to a specific finding below.
        </p>
      </div>

      {/* Issues table */}
      {report.top_issues && report.top_issues.length > 0 && (
        <div className="glass-card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "18px 24px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 10 }}>
            <AlertTriangle size={16} color="var(--warning)" />
            <h3 style={{ fontSize: "1rem", fontWeight: 700 }}>
              Top Issues ({report.top_issues.length})
            </h3>
          </div>
          <div>
            {report.top_issues.map((issue, i) => {
              const sev = SEVERITY_MAP[issue.severity] || SEVERITY_MAP.info;
              const filename = issue.file_path?.split("/").pop() ?? issue.file_path;
              return (
                <div
                  key={i}
                  style={{
                    padding: "14px 24px",
                    borderBottom: i < report.top_issues.length - 1 ? "1px solid var(--border)" : "none",
                    display: "grid",
                    gridTemplateColumns: "auto 1fr auto",
                    gap: 16,
                    alignItems: "center",
                  }}
                >
                  <span className={`badge ${sev.cls}`}>{sev.label}</span>
                  <div>
                    <div style={{ fontSize: "0.875rem", marginBottom: 3 }}>{issue.message}</div>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                      {issue.tool} · {issue.file_path}:{issue.line}
                    </div>
                  </div>
                  <span className="badge badge-muted" style={{ fontSize: "0.72rem" }}>{issue.tool}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
