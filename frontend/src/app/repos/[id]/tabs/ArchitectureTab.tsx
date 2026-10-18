"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import { api, type ArchitectureData } from "@/lib/api";
import { Loader2, AlertCircle, Maximize2, Minimize2, Info } from "lucide-react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  MarkerType,
  useNodesState,
  useEdgesState,
  Panel,
  type NodeTypes,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

/* ─── Custom Node Component ──────────────────────────────────────────────── */

function ComponentNode({ data }: { data: any }) {
  const isExternal = data.nodeType === "external";
  const fileCount = data.fileCount || 0;

  return (
    <div
      style={{
        background: isExternal
          ? "linear-gradient(135deg, rgba(168,85,247,0.15), rgba(139,92,246,0.08))"
          : "linear-gradient(135deg, rgba(99,102,241,0.2), rgba(79,70,229,0.08))",
        border: `1.5px solid ${isExternal ? "rgba(168,85,247,0.4)" : "rgba(99,102,241,0.4)"}`,
        borderRadius: 12,
        padding: "12px 16px",
        minWidth: 160,
        maxWidth: 260,
        backdropFilter: "blur(12px)",
        boxShadow: `0 4px 20px ${isExternal ? "rgba(168,85,247,0.1)" : "rgba(99,102,241,0.1)"}`,
        transition: "all 0.2s ease",
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: "rgba(99,102,241,0.6)", border: "none", width: 6, height: 6 }}
      />

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: isExternal
              ? "linear-gradient(135deg, #a855f7, #7c3aed)"
              : "linear-gradient(135deg, #6366f1, #4f46e5)",
            flexShrink: 0,
          }}
        />
        <div
          style={{
            fontWeight: 600,
            fontSize: "0.8rem",
            color: "#f1f5f9",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
          title={data.label}
        >
          {data.label}
        </div>
      </div>

      {/* File count badge */}
      {fileCount > 0 && !isExternal && (
        <div
          style={{
            fontSize: "0.68rem",
            color: "rgba(148,163,184,0.8)",
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          <span style={{ fontFamily: "var(--font-mono, monospace)" }}>{fileCount}</span>
          <span>{fileCount === 1 ? "file" : "files"}</span>
        </div>
      )}

      {/* Files preview */}
      {data.files && data.files.length > 0 && !isExternal && (
        <div
          style={{
            marginTop: 8,
            padding: "6px 8px",
            background: "rgba(0,0,0,0.2)",
            borderRadius: 6,
            maxHeight: 72,
            overflowY: "auto",
          }}
        >
          {data.files.slice(0, 4).map((f: string, i: number) => {
            const basename = f.split("/").pop() || f;
            return (
              <div
                key={i}
                style={{
                  fontSize: "0.62rem",
                  color: "rgba(148,163,184,0.7)",
                  fontFamily: "var(--font-mono, monospace)",
                  lineHeight: 1.6,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={f}
              >
                {basename}
              </div>
            );
          })}
          {data.files.length > 4 && (
            <div style={{ fontSize: "0.6rem", color: "rgba(99,102,241,0.7)", marginTop: 2 }}>
              +{data.files.length - 4} more
            </div>
          )}
        </div>
      )}

      {isExternal && (
        <div style={{ fontSize: "0.65rem", color: "rgba(168,85,247,0.6)", marginTop: 2 }}>
          external dependency
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: "rgba(99,102,241,0.6)", border: "none", width: 6, height: 6 }}
      />
    </div>
  );
}

const nodeTypes: NodeTypes = {
  component: ComponentNode,
};

/* ─── Layout Helpers ─────────────────────────────────────────────────────── */

function computeLayout(
  components: ArchitectureData["components"],
  relationships: ArchitectureData["relationships"]
): { nodes: Node[]; edges: Edge[] } {
  // Separate internal and external nodes
  const internals = components.filter((c) => c.type !== "external");
  const externals = components.filter((c) => c.type === "external");

  // Compute edge counts per node for sizing
  const edgeCounts: Record<string, number> = {};
  for (const r of relationships) {
    edgeCounts[r.from] = (edgeCounts[r.from] || 0) + (r.weight || 1);
    edgeCounts[r.to] = (edgeCounts[r.to] || 0) + (r.weight || 1);
  }

  // Layout internals in a grid with spacing
  const internalCols = Math.max(2, Math.ceil(Math.sqrt(internals.length)));
  const CELL_W = 300;
  const CELL_H = 200;

  const nodes: Node[] = [];

  internals.forEach((comp, i) => {
    const col = i % internalCols;
    const row = Math.floor(i / internalCols);
    nodes.push({
      id: comp.id,
      type: "component",
      position: { x: col * CELL_W + Math.random() * 30, y: row * CELL_H + Math.random() * 20 },
      data: {
        label: comp.label,
        files: comp.files,
        nodeType: comp.type || "internal",
        fileCount: comp.fileCount || comp.files.length,
      },
    });
  });

  // Layout externals in a row below internals
  const internalRows = Math.ceil(internals.length / internalCols);
  const extStartY = internalRows * CELL_H + 120;
  const extCols = Math.max(3, Math.ceil(Math.sqrt(externals.length)));
  const EXT_CELL_W = 220;

  externals.forEach((comp, i) => {
    const col = i % extCols;
    const row = Math.floor(i / extCols);
    nodes.push({
      id: comp.id,
      type: "component",
      position: { x: col * EXT_CELL_W, y: extStartY + row * 160 },
      data: {
        label: comp.label,
        files: comp.files,
        nodeType: "external",
        fileCount: 0,
      },
    });
  });

  // Build edges
  const edgeTypeColors: Record<string, string> = {
    calls: "#22d3ee",
    imports: "#6366f1",
    extends: "#f59e0b",
    depends_on: "#10b981",
  };

  const edges: Edge[] = relationships.map((rel, i) => ({
    id: `e-${i}`,
    source: rel.from,
    target: rel.to,
    type: "default",
    animated: rel.type === "calls",
    label: `${rel.type}${rel.weight && rel.weight > 1 ? ` (${rel.weight})` : ""}`,
    labelStyle: {
      fontSize: 10,
      fill: "rgba(148,163,184,0.8)",
      fontWeight: 500,
    },
    labelBgStyle: {
      fill: "rgba(15,23,42,0.85)",
      fillOpacity: 0.85,
    },
    labelBgPadding: [6, 3] as [number, number],
    labelBgBorderRadius: 4,
    style: {
      stroke: edgeTypeColors[rel.type] || "#475569",
      strokeWidth: Math.min(3, 1 + (rel.weight || 1) * 0.3),
      opacity: 0.7,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 14,
      height: 14,
      color: edgeTypeColors[rel.type] || "#475569",
    },
  }));

  return { nodes, edges };
}

/* ─── Main Component ─────────────────────────────────────────────────────── */

export default function ArchitectureTab({ repoId }: { repoId: string }) {
  const [data, setData] = useState<ArchitectureData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [showLegend, setShowLegend] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const arch = await api.architecture.get(repoId);
        setData(arch);

        if (arch.components.length > 0) {
          const layout = computeLayout(arch.components, arch.relationships);
          setNodes(layout.nodes);
          setEdges(layout.edges);
        }
      } catch (err: any) {
        setError(err.message || "Failed to load architecture data");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [repoId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 500 }}>
        <div style={{ textAlign: "center" }}>
          <Loader2
            size={36}
            color="var(--primary)"
            className="animate-spin"
            style={{ margin: "0 auto 16px" }}
          />
          <p style={{ color: "var(--text-secondary)" }}>Analyzing architecture…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="glass-card"
        style={{ padding: 32, textAlign: "center", color: "var(--danger)" }}
      >
        <AlertCircle size={32} style={{ margin: "0 auto 12px" }} />
        <p>{error}</p>
      </div>
    );
  }

  if (!data || data.components.length === 0) {
    return (
      <div className="glass-card" style={{ padding: 48, textAlign: "center" }}>
        <div
          style={{
            width: 64,
            height: 64,
            borderRadius: "50%",
            background: "rgba(99,102,241,0.1)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 16px",
          }}
        >
          <Info size={28} color="rgba(99,102,241,0.5)" />
        </div>
        <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: 8 }}>
          No Architecture Data
        </h3>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", maxWidth: 400, margin: "0 auto" }}>
          Architecture data is generated during indexing. This repository may not have enough
          inter-module relationships to display, or indexing may still be in progress.
        </p>
      </div>
    );
  }

  const internalCount = data.components.filter((c) => c.type !== "external").length;
  const externalCount = data.components.filter((c) => c.type === "external").length;

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: 8 }}>
          Architecture Overview
        </h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          Interactive dependency graph built from real import and call patterns.
          <span style={{ color: "var(--text-muted)", marginLeft: 8 }}>
            Drag to pan · Scroll to zoom · Drag nodes to rearrange
          </span>
        </p>
      </div>

      {/* Stats Bar */}
      <div
        style={{
          display: "flex",
          gap: 16,
          marginBottom: 16,
          flexWrap: "wrap",
        }}
      >
        <StatPill label="Modules" value={internalCount} color="#6366f1" />
        <StatPill label="External Deps" value={externalCount} color="#a855f7" />
        <StatPill label="Relationships" value={data.relationships.length} color="#22d3ee" />
      </div>

      {/* Graph Container */}
      <div
        className="glass-card"
        style={{
          height: 600,
          borderRadius: 16,
          overflow: "hidden",
          position: "relative",
        }}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          minZoom={0.1}
          maxZoom={2.5}
          proOptions={{ hideAttribution: true }}
          style={{ background: "#0a0f1e" }}
        >
          <Background color="rgba(99,102,241,0.06)" gap={40} size={1} />
          <Controls
            showInteractive={false}
            style={{
              borderRadius: 10,
              overflow: "hidden",
              border: "1px solid rgba(99,102,241,0.2)",
              background: "rgba(15,23,42,0.9)",
              boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
            }}
          />
          <MiniMap
            nodeStrokeColor={(n: Node) =>
              n.data?.nodeType === "external"
                ? "rgba(168,85,247,0.5)"
                : "rgba(99,102,241,0.5)"
            }
            nodeColor={(n: Node) =>
              n.data?.nodeType === "external"
                ? "rgba(168,85,247,0.3)"
                : "rgba(99,102,241,0.3)"
            }
            maskColor="rgba(10,15,30,0.85)"
            style={{
              borderRadius: 8,
              border: "1px solid rgba(99,102,241,0.15)",
              background: "rgba(15,23,42,0.9)",
            }}
          />

          {/* Legend Panel */}
          {showLegend && (
            <Panel position="top-right">
              <div
                style={{
                  background: "rgba(15,23,42,0.92)",
                  border: "1px solid rgba(99,102,241,0.15)",
                  borderRadius: 12,
                  padding: "14px 18px",
                  backdropFilter: "blur(12px)",
                  fontSize: "0.75rem",
                  minWidth: 170,
                }}
              >
                <div
                  style={{
                    fontWeight: 600,
                    marginBottom: 10,
                    color: "#f1f5f9",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  Legend
                  <button
                    onClick={() => setShowLegend(false)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "rgba(148,163,184,0.6)",
                      cursor: "pointer",
                      fontSize: "0.7rem",
                      padding: "2px 4px",
                    }}
                  >
                    ✕
                  </button>
                </div>
                <LegendItem color="#22d3ee" label="calls" dashed={false} animated />
                <LegendItem color="#6366f1" label="imports" dashed={false} />
                <LegendItem color="#f59e0b" label="extends" dashed={false} />
                <LegendItem color="#10b981" label="depends_on" dashed={false} />
                <div
                  style={{
                    borderTop: "1px solid rgba(99,102,241,0.1)",
                    margin: "8px 0",
                    paddingTop: 8,
                  }}
                >
                  <LegendNode color="#6366f1" label="Internal module" />
                  <LegendNode color="#a855f7" label="External package" />
                </div>
              </div>
            </Panel>
          )}

          {!showLegend && (
            <Panel position="top-right">
              <button
                onClick={() => setShowLegend(true)}
                style={{
                  background: "rgba(15,23,42,0.9)",
                  border: "1px solid rgba(99,102,241,0.2)",
                  borderRadius: 8,
                  padding: "6px 12px",
                  color: "#94a3b8",
                  cursor: "pointer",
                  fontSize: "0.75rem",
                }}
              >
                <Info size={14} style={{ marginRight: 4, verticalAlign: "middle" }} />
                Legend
              </button>
            </Panel>
          )}
        </ReactFlow>
      </div>
    </div>
  );
}

/* ─── Utility Components ─────────────────────────────────────────────────── */

function StatPill({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 14px",
        background: `${color}10`,
        border: `1px solid ${color}30`,
        borderRadius: 20,
        fontSize: "0.82rem",
      }}
    >
      <span style={{ fontWeight: 700, color, fontFamily: "var(--font-mono, monospace)" }}>
        {value}
      </span>
      <span style={{ color: "rgba(148,163,184,0.8)" }}>{label}</span>
    </div>
  );
}

function LegendItem({
  color,
  label,
  dashed,
  animated,
}: {
  color: string;
  label: string;
  dashed?: boolean;
  animated?: boolean;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
      <div style={{ position: "relative", width: 24, height: 2 }}>
        <div
          style={{
            width: "100%",
            height: 2,
            background: color,
            borderStyle: dashed ? "dashed" : "solid",
            opacity: 0.8,
          }}
        />
        {animated && (
          <div
            style={{
              position: "absolute",
              top: -1,
              left: 0,
              width: 4,
              height: 4,
              borderRadius: "50%",
              background: color,
              animation: "legendPulse 1.5s infinite",
            }}
          />
        )}
      </div>
      <span style={{ color: "rgba(148,163,184,0.7)" }}>{label}</span>
    </div>
  );
}

function LegendNode({ color, label }: { color: string; label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
      <div
        style={{
          width: 10,
          height: 10,
          borderRadius: 3,
          background: `${color}30`,
          border: `1.5px solid ${color}60`,
        }}
      />
      <span style={{ color: "rgba(148,163,184,0.7)" }}>{label}</span>
    </div>
  );
}
