"use client";

import { useEffect, useState, useCallback } from "react";
import { api, type ArchitectureData } from "@/lib/api";
import { Loader2, AlertCircle, ZoomIn, ZoomOut } from "lucide-react";

function generateMermaid(data: ArchitectureData): string {
  const lines = ["flowchart TD"];
  // Nodes
  for (const comp of data.components) {
    const safeId = comp.id.replace(/[^a-zA-Z0-9_]/g, "_");
    const label = comp.label.replace(/"/g, "'");
    lines.push(`    ${safeId}["${label}"]`);
  }
  // Edges
  for (const rel of data.relationships) {
    const from = rel.from.replace(/[^a-zA-Z0-9_]/g, "_");
    const to = rel.to.replace(/[^a-zA-Z0-9_]/g, "_");
    const label = rel.type;
    lines.push(`    ${from} -->|"${label}"| ${to}`);
  }
  return lines.join("\n");
}

export default function ArchitectureTab({ repoId }: { repoId: string }) {
  const [data, setData] = useState<ArchitectureData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mermaidSvg, setMermaidSvg] = useState<string>("");

  useEffect(() => {
    const load = async () => {
      try {
        const arch = await api.architecture.get(repoId);
        setData(arch);

        // Render mermaid
        const { default: mermaid } = await import("mermaid");
        mermaid.initialize({
          startOnLoad: false,
          theme: "dark",
          themeVariables: {
            darkMode: true,
            background: "#0d1526",
            primaryColor: "#6366f1",
            primaryTextColor: "#f1f5f9",
            primaryBorderColor: "rgba(99,102,241,0.4)",
            lineColor: "#475569",
            secondaryColor: "#1e2d4a",
            tertiaryColor: "#111827",
            fontSize: "14px",
          },
        });

        const mermaidCode = generateMermaid(arch);
        const { svg } = await mermaid.render("arch-diagram", mermaidCode);
        setMermaidSvg(svg);
      } catch (err: any) {
        setError(err.message || "Failed to load architecture diagram");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [repoId]);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 400 }}>
        <div style={{ textAlign: "center" }}>
          <Loader2 size={36} color="var(--primary)" className="animate-spin" style={{ margin: "0 auto 16px" }} />
          <p style={{ color: "var(--text-secondary)" }}>Loading architecture diagram…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card" style={{ padding: 32, textAlign: "center", color: "var(--danger)" }}>
        <AlertCircle size={32} style={{ margin: "0 auto 12px" }} />
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: 8 }}>Architecture Overview</h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          Component-level graph derived from the knowledge graph. Shows module relationships extracted from real import and call patterns.
        </p>
      </div>

      {/* Diagram */}
      <div
        className="glass-card"
        style={{
          padding: 24,
          overflow: "auto",
          minHeight: 400,
        }}
      >
        {mermaidSvg ? (
          <div
            dangerouslySetInnerHTML={{ __html: mermaidSvg }}
            style={{ display: "flex", justifyContent: "center" }}
          />
        ) : (
          <div style={{ textAlign: "center", padding: "48px 0", color: "var(--text-muted)" }}>
            No architecture data available yet
          </div>
        )}
      </div>

      {/* Component list */}
      {data && data.components.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 14 }}>
            Components ({data.components.length})
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
            {data.components.map((comp) => (
              <div key={comp.id} className="glass-card" style={{ padding: 16 }}>
                <div style={{ fontWeight: 600, marginBottom: 8, fontSize: "0.9rem" }}>{comp.label}</div>
                <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
                  {comp.files.slice(0, 3).map((f) => (
                    <div key={f} style={{ fontFamily: "var(--font-mono)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {f}
                    </div>
                  ))}
                  {comp.files.length > 3 && (
                    <div style={{ color: "var(--primary-light)" }}>+{comp.files.length - 3} more</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
