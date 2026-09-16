"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { GitFork, Zap, GitBranch, Shield, BarChart3, MessageSquare, ArrowRight, Star, Code2, Network } from "lucide-react";
import { getAccessToken } from "@/lib/api";

const FEATURES = [
  {
    icon: Network,
    title: "Engineering Knowledge Graph",
    description:
      "We parse your entire codebase with Tree-sitter to build a real structural graph — functions, classes, imports, call chains. Not chunks. Not summaries. The actual architecture.",
    color: "var(--primary)",
    glow: "rgba(99, 102, 241, 0.3)",
  },
  {
    icon: MessageSquare,
    title: "Grounded AI Chat",
    description:
      "Ask anything about your codebase. Every answer is grounded in both the knowledge graph (structured facts) and semantic embeddings. Citations point to the exact file and line.",
    color: "var(--accent)",
    glow: "rgba(6, 182, 212, 0.3)",
  },
  {
    icon: GitBranch,
    title: "Feature Tracing",
    description:
      "\"Trace the login flow.\" DevLens identifies the entry point, walks the call graph, and shows you the ordered path from frontend to database — clickable at every step.",
    color: "#a78bfa",
    glow: "rgba(167, 139, 250, 0.3)",
  },
  {
    icon: Code2,
    title: "Architecture Visualization",
    description:
      "An interactive diagram generated from the real graph, not a static template. See how your modules connect, click into any component, and explore the dependency structure.",
    color: "#34d399",
    glow: "rgba(52, 211, 153, 0.3)",
  },
  {
    icon: Shield,
    title: "Security Analysis",
    description:
      "Real static analysis via Ruff, Bandit, and ESLint. Critical vulnerabilities, security anti-patterns, and code quality issues surfaced with exact file/line references.",
    color: "#fb923c",
    glow: "rgba(251, 146, 60, 0.3)",
  },
  {
    icon: BarChart3,
    title: "Health Report",
    description:
      "A transparent, formula-based health score across complexity, security, duplication, and dependency staleness. Every point deducted is explained. No black-box AI scores.",
    color: "#fbbf24",
    glow: "rgba(251, 191, 36, 0.3)",
  },
];

const STEPS = [
  { step: "01", title: "Paste a GitHub URL", desc: "Any public repository. We handle the rest." },
  { step: "02", title: "Automatic indexing", desc: "Clone → AST parse → Graph build → Embeddings → Analysis. ~15 min for repos up to 50k LOC." },
  { step: "03", title: "Explore & understand", desc: "Chat, trace features, view the architecture, read the health report — all grounded in the real codebase structure." },
];

// Animated counter
function Counter({ target, suffix = "" }: { target: number; suffix?: string }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    let start = 0;
    const duration = 1500;
    const step = (target / duration) * 16;
    const timer = setInterval(() => {
      start += step;
      if (start >= target) {
        setCount(target);
        clearInterval(timer);
      } else {
        setCount(Math.floor(start));
      }
    }, 16);
    return () => clearInterval(timer);
  }, [target]);
  return <span>{count.toLocaleString()}{suffix}</span>;
}

export default function LandingPage() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    setIsLoggedIn(!!getAccessToken());
  }, []);

  return (
    <div className="page-layout">
      {/* ── Nav ──────────────────────────────────────────────────────────── */}
      <nav className="nav">
        <div className="container" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", height: 64 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: "linear-gradient(135deg, var(--primary), var(--accent))", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Zap size={18} color="white" />
            </div>
            <span style={{ fontWeight: 800, fontSize: "1.1rem", letterSpacing: "-0.03em" }}>
              Dev<span className="gradient-text">Lens</span>
            </span>
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <a href="https://github.com" target="_blank" rel="noopener" className="btn-ghost" style={{ padding: "8px 14px" }}>
              <GitFork size={16} /> GitHub
            </a>
            {isLoggedIn ? (
              <Link href="/dashboard" className="btn-primary" style={{ padding: "8px 18px" }}>
                Dashboard <ArrowRight size={15} />
              </Link>
            ) : (
              <Link href="/auth" className="btn-primary" style={{ padding: "8px 18px" }}>
                Sign in
              </Link>
            )}
          </div>
        </div>
      </nav>

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section style={{ padding: "120px 0 80px", textAlign: "center" }}>
        <div className="container">
          {/* Badge */}
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 28 }}>
            <span className="badge badge-primary animate-fade-in" style={{ fontSize: "0.8rem", padding: "6px 16px" }}>
              <Star size={12} /> Open Source · Zero-Cost MVP · Real Parsing, Real Graph
            </span>
          </div>

          {/* Headline */}
          <h1
            className="animate-fade-in-up"
            style={{ fontSize: "clamp(2.8rem, 7vw, 5.5rem)", fontWeight: 900, lineHeight: 1.05, marginBottom: 24, letterSpacing: "-0.04em" }}
          >
            Understand any codebase
            <br />
            <span className="gradient-text">in 15 minutes.</span>
          </h1>

          {/* Sub */}
          <p
            className="animate-fade-in-up"
            style={{ fontSize: "clamp(1rem, 2vw, 1.25rem)", color: "var(--text-secondary)", maxWidth: 640, margin: "0 auto 48px", lineHeight: 1.7, animationDelay: "80ms" }}
          >
            DevLens AI parses your GitHub repository into an Engineering Knowledge Graph,
            then answers your questions, traces features, and visualizes architecture — all
            grounded in the{" "}
            <em style={{ color: "var(--text-primary)", fontStyle: "normal", fontWeight: 600 }}>actual structure</em> of your code.
          </p>

          {/* CTA */}
          <div className="animate-fade-in-up" style={{ display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap", animationDelay: "160ms" }}>
            {isLoggedIn ? (
              <Link href="/dashboard" className="btn-primary" style={{ fontSize: "1rem", padding: "14px 32px" }}>
                Go to Dashboard <ArrowRight size={18} />
              </Link>
            ) : (
              <Link href="/auth" className="btn-primary" style={{ fontSize: "1rem", padding: "14px 32px" }}>
                Get started free <ArrowRight size={18} />
              </Link>
            )}
            <a href="#how-it-works" className="btn-ghost" style={{ fontSize: "1rem", padding: "14px 32px" }}>
              See how it works
            </a>
          </div>

          {/* Stats */}
          <div
            className="animate-fade-in-up"
            style={{
              display: "flex",
              gap: 48,
              justifyContent: "center",
              marginTop: 72,
              flexWrap: "wrap",
              animationDelay: "240ms",
            }}
          >
            {[
              { value: 50000, suffix: "+", label: "Lines of code supported" },
              { value: 15, suffix: " min", label: "Average indexing time" },
              { value: 4, suffix: "", label: "Health metrics computed" },
            ].map((stat, i) => (
              <div key={i} style={{ textAlign: "center" }}>
                <div style={{ fontSize: "2.5rem", fontWeight: 900, background: "linear-gradient(135deg, var(--primary-light), var(--accent))", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                  <Counter target={stat.value} suffix={stat.suffix} />
                </div>
                <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: 4 }}>{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ─────────────────────────────────────────────────────── */}
      <section style={{ padding: "80px 0" }}>
        <div className="container">
          <div style={{ textAlign: "center", marginBottom: 56 }}>
            <h2 style={{ fontSize: "clamp(1.8rem, 4vw, 2.8rem)", marginBottom: 16 }}>
              Real intelligence, not{" "}
              <span className="gradient-text">\"chunk and embed\"</span>
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "1.05rem", maxWidth: 560, margin: "0 auto" }}>
              Every feature is backed by actual static analysis and graph traversal — not
              LLM hallucinations about code it's never really seen.
            </p>
          </div>

          <div
            className="stagger"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
              gap: 20,
            }}
          >
            {FEATURES.map((f, i) => (
              <div
                key={i}
                className="glass-card animate-fade-in-up"
                style={{ padding: 28, cursor: "default" }}
              >
                <div
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 12,
                    background: `radial-gradient(circle at 30% 30%, ${f.glow}, transparent)`,
                    border: `1px solid ${f.color}30`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginBottom: 18,
                  }}
                >
                  <f.icon size={22} color={f.color} />
                </div>
                <h3 style={{ fontSize: "1.05rem", marginBottom: 10, color: "var(--text-primary)" }}>{f.title}</h3>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", lineHeight: 1.7 }}>{f.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────────────────────── */}
      <section id="how-it-works" style={{ padding: "80px 0" }}>
        <div className="container">
          <div style={{ textAlign: "center", marginBottom: 56 }}>
            <h2 style={{ fontSize: "clamp(1.8rem, 4vw, 2.8rem)", marginBottom: 16 }}>
              From URL to insight in{" "}
              <span className="gradient-text">three steps</span>
            </h2>
          </div>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", justifyContent: "center" }}>
            {STEPS.map((s, i) => (
              <div key={i} className="glass-card" style={{ flex: "1 1 260px", maxWidth: 320, padding: 32, position: "relative" }}>
                <div style={{ fontSize: "3.5rem", fontWeight: 900, color: "var(--border)", lineHeight: 1, marginBottom: 16, fontVariantNumeric: "tabular-nums" }}>
                  {s.step}
                </div>
                <h3 style={{ fontSize: "1.1rem", marginBottom: 10 }}>{s.title}</h3>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", lineHeight: 1.7 }}>{s.desc}</p>
                {i < STEPS.length - 1 && (
                  <div style={{ position: "absolute", right: -24, top: "50%", transform: "translateY(-50%)", color: "var(--border)", display: "none" }}>
                    <ArrowRight size={20} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────────────────── */}
      <section style={{ padding: "80px 0 120px", textAlign: "center" }}>
        <div className="container">
          <div
            className="glass-card animate-pulse-glow"
            style={{ maxWidth: 680, margin: "0 auto", padding: "60px 40px" }}
          >
            <h2 style={{ fontSize: "clamp(1.8rem, 4vw, 2.8rem)", marginBottom: 16 }}>
              Ready to understand your codebase?
            </h2>
            <p style={{ color: "var(--text-secondary)", marginBottom: 36, fontSize: "1.05rem" }}>
              Free to use. No credit card. No setup. Just a GitHub URL.
            </p>
            {isLoggedIn ? (
              <Link href="/dashboard" className="btn-primary" style={{ fontSize: "1.05rem", padding: "16px 40px" }}>
                Go to Dashboard <ArrowRight size={18} />
              </Link>
            ) : (
              <a href="/api/auth/github" className="btn-primary" style={{ fontSize: "1.05rem", padding: "16px 40px" }}>
                <GitFork size={18} /> Sign in with GitHub — it's free
              </a>
            )}
          </div>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────────── */}
      <footer style={{ borderTop: "1px solid var(--border)", padding: "32px 0", textAlign: "center" }}>
        <div className="container" style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
          <p>
            DevLens AI — Built with Next.js, FastAPI, Tree-sitter, and pgvector.
            <span style={{ margin: "0 12px", opacity: 0.4 }}>·</span>
            <a href="https://github.com" style={{ color: "var(--text-secondary)", textDecoration: "none" }}>
              Open Source
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
