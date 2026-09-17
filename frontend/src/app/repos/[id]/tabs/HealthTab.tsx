"use client";

import { useEffect, useState } from "react";
import { api, type HealthReport } from "@/lib/api";
import {
  Loader2,
  AlertCircle,
  Shield,
  Zap,
  Clock,
  AlertTriangle,
  CheckCircle2,
  AlertOctagon,
  GitMerge,
  FileCode,
  Check,
} from "lucide-react";

// ── Score gauge ───────────────────────────────────────────────────────────────

function ScoreGauge({ score, label, sublabel, size = 88 }: { score: number; label: string; sublabel?: string; size?: number }) {
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
      <div style={{ marginTop: size / 2 - 8, fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: 600 }}>{label}</div>
      {sublabel && <div style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>{sublabel}</div>}
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

  const metrics = report.metrics_json;
  const qualityScore = report.code_quality_score ?? report.duplication_score;

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 28, flexWrap: "wrap", gap: 16 }}>
        <div>
          <h2 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: 6 }}>Repository Health Report</h2>
          <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-muted)", fontSize: "0.82rem" }}>
            <Clock size={13} /> Generated {generatedAt}
          </div>
        </div>
        {/* Overall score big display */}
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "3.75rem", fontWeight: 900, color: scoreColor, lineHeight: 1 }}>
            {report.overall_score}
          </div>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 2 }}>Overall Health / 100</div>
        </div>
      </div>

      {/* Audit Trail & Transparency Cards */}
      {metrics && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16, marginBottom: 24 }}>
          {/* 1. Ceiling Status Card */}
          <div className="glass-card" style={{ padding: "18px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              {metrics.ceiling.triggered ? (
                <>
                  <AlertOctagon size={16} color="var(--danger)" />
                  <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--danger)" }}>
                    Ceiling Enforced (Cap: {metrics.ceiling.level === "critical" ? 70 : 85})
                  </span>
                </>
              ) : (
                <>
                  <CheckCircle2 size={16} color="var(--success)" />
                  <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--success)" }}>
                    Ceiling Cleared (Uncapped)
                  </span>
                </>
              )}
            </div>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", lineHeight: 1.5, margin: 0 }}>
              {metrics.ceiling.triggered
                ? `Capped due to production rule ${metrics.ceiling.trigger_rule} in ${metrics.ceiling.trigger_file}`
                : "No ship-blocking critical/high vulnerabilities detected in production runtime code."}
            </p>
          </div>

          {/* 2. Dual-Detection Dedup Card */}
          <div className="glass-card" style={{ padding: "18px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <GitMerge size={16} color="var(--primary)" />
              <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-primary)" }}>
                Dual-Detection Dedup ({metrics.dedup_summary.dual_detection_overlaps} merged)
              </span>
            </div>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", lineHeight: 1.5, margin: 0 }}>
              {metrics.dedup_summary.dual_detection_overlaps > 0
                ? `${metrics.dedup_summary.dual_detection_overlaps} overlapping findings between Ruff (Flake8-Bandit) & Bandit collapsed via proximity matching (±2 lines).`
                : "Zero dual-detection collisions between Ruff & Bandit findings."}
            </p>
          </div>

          {/* 3. Codebase Scope Card */}
          <div className="glass-card" style={{ padding: "18px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <FileCode size={16} color="var(--text-secondary)" />
              <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-primary)" }}>
                {metrics.total_loc?.toLocaleString()} LOC ({metrics.kloc} KLOC)
              </span>
            </div>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", lineHeight: 1.5, margin: 0 }}>
              Normalized defect density across {metrics.dependency.total_files} files. Weighted: Crit 15×, High 6×, Med 2×, Low 0.4×, Info 0.02×.
            </p>
          </div>
        </div>
      )}

      {/* Score breakdown gauges */}
      <div className="glass-card" style={{ padding: 24, marginBottom: 24 }}>
        <h3 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: 20, color: "var(--text-secondary)" }}>
          Sub-Score Breakdown
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 20 }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <ScoreGauge score={report.security_score} label="Security" sublabel="Bandit + Ruff S" />
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <ScoreGauge score={qualityScore} label="Code Quality" sublabel="Logic & Smells" />
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <ScoreGauge score={report.complexity_score} label="Complexity" sublabel="AST Function/Class" />
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <ScoreGauge score={report.dependency_score} label="Dependencies" sublabel="Graph & Coupling" />
          </div>
        </div>
      </div>

      {/* Formula transparency box */}
      <div className="glass-card" style={{ padding: 20, marginBottom: 24, borderLeft: "3px solid var(--primary)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, fontSize: "0.85rem", fontWeight: 600, color: "var(--primary-light)" }}>
          <Zap size={14} /> Mathematical Model Transparency
        </div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "var(--text-primary)", marginBottom: 8, background: "rgba(0,0,0,0.2)", padding: "8px 12px", borderRadius: 6 }}>
          Overall ({report.overall_score}) = round(0.35 × Sec({report.security_score}) + 0.30 × Quality({qualityScore}) + 0.20 × Comp({report.complexity_score}) + 0.15 × Dep({report.dependency_score}))
        </div>
        <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", lineHeight: 1.6, margin: 0 }}>
          Scores are size-normalized per KLOC. Developer maintenance scripts, examples, and test fixtures count toward defect density but are exempted from the hard ship-blocker ceiling (caps to 70/85), preventing false-positive production blocks.
        </p>
      </div>

      {/* Issues table */}
      {report.top_issues && report.top_issues.length > 0 && (
        <div className="glass-card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <AlertTriangle size={16} color="var(--warning)" />
              <h3 style={{ fontSize: "0.95rem", fontWeight: 700 }}>
                Top Static Analysis Issues ({report.top_issues.length})
              </h3>
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              Sorted by severity hierarchy
            </div>
          </div>
          <div>
            {report.top_issues.map((issue, i) => {
              const sev = SEVERITY_MAP[issue.severity.toLowerCase()] || SEVERITY_MAP.info;
              return (
                <div
                  key={i}
                  style={{
                    padding: "12px 20px",
                    borderBottom: i < report.top_issues.length - 1 ? "1px solid var(--border)" : "none",
                    display: "grid",
                    gridTemplateColumns: "auto 1fr auto",
                    gap: 14,
                    alignItems: "center",
                  }}
                >
                  <div style={{ display: "flex", flexDirection: "column", gap: 4, alignItems: "flex-start" }}>
                    <span className={`badge ${sev.cls}`}>{sev.label}</span>
                    {issue.rule_id && (
                      <span style={{ fontSize: "0.68rem", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                        {issue.rule_id}
                      </span>
                    )}
                  </div>
                  <div>
                    <div style={{ fontSize: "0.85rem", marginBottom: 3, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <span>{issue.message}</span>
                      {issue.is_non_production && (
                        <span
                          className="badge badge-warning"
                          style={{ fontSize: "0.68rem", padding: "1px 6px" }}
                          title="Counted in defect density, but exempted from production ship-blocker ceiling"
                        >
                          Developer Tooling / Fixture (Ceiling-Exempt)
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: "0.76rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                      {issue.tool} · {issue.file_path}:{issue.line}
                    </div>
                  </div>
                  <span className="badge badge-muted" style={{ fontSize: "0.7rem" }}>{issue.tool}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
