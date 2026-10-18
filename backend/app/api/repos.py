"""
DevLens AI — Repository API Router
CRUD for repositories + job status polling + analysis endpoints.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, case, text as sa_text

import structlog

from app.auth.dependencies import CurrentUserId
from app.database import get_db_context

from app.models import (
    IndexingJob, Repository, HealthReport as HealthReportModel,
    GraphNode, GraphEdge, StaticAnalysisResult, File, Embedding
)

router = APIRouter(prefix="/repositories", tags=["repositories"])
logger = structlog.get_logger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class RepositoryImportRequest(BaseModel):
    source_url: str  # e.g. "https://github.com/owner/repo"


class RepositoryOut(BaseModel):
    id: uuid.UUID
    name: str
    full_name: str
    source_url: str
    primary_language: Optional[str]
    health_score: Optional[int]
    status: str
    last_indexed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportResponse(BaseModel):
    repository_id: uuid.UUID
    job_id: uuid.UUID
    status: str


class JobStatusOut(BaseModel):
    job_id: uuid.UUID
    repository_id: uuid.UUID
    stage: str
    progress_pct: int
    error_message: Optional[str]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_github_url(url: str) -> tuple[str, str]:
    """Extract (owner, repo_name) from a GitHub URL. Returns ('', '') if invalid."""
    try:
        url = url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        parts = url.split("github.com/")[-1].split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
    except Exception:
        pass
    return "", ""


async def _verify_repo_access(db, repository_id: uuid.UUID, user_id: uuid.UUID) -> Repository:
    """Verify user owns the repository and return it; raise 404 otherwise."""
    result = await db.execute(
        select(Repository).where(
            Repository.id == repository_id,
            Repository.owner_user_id == user_id,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


# ── CRUD Routes ───────────────────────────────────────────────────────────────

@router.post("", response_model=ImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_repository(body: RepositoryImportRequest, user_id: CurrentUserId):
    """
    Import a new repository (FR-2.1, FR-2.2).
    Validates the URL, creates a repository record, and enqueues the processing pipeline.
    """
    source_url = body.source_url.strip()

    # Basic GitHub URL validation
    if "github.com" not in source_url:
        raise HTTPException(status_code=400, detail="Only public GitHub URLs are supported in V1")

    owner, repo_name = _parse_github_url(source_url)
    if not owner or not repo_name:
        raise HTTPException(status_code=400, detail="Could not parse owner/repo from the provided URL")

    full_name = f"{owner}/{repo_name}"

    async with get_db_context() as db:
        # Check for duplicate import (FR-2.1 conflict)
        existing = await db.execute(
            select(Repository).where(
                Repository.owner_user_id == user_id,
                Repository.source_url == source_url,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=422,
                detail="This repository has already been imported. Use /reindex to refresh it.",
            )

        # Create repository record
        repo = Repository(
            owner_user_id=user_id,
            name=repo_name,
            full_name=full_name,
            source_url=source_url,
            status="pending",
        )
        db.add(repo)
        await db.flush()

        # Create indexing job
        job = IndexingJob(
            repository_id=repo.id,
            stage="pending",
            progress_pct=0,
        )
        db.add(job)
        await db.flush()

        repo_id = repo.id
        job_id = job.id

    # Enqueue Celery pipeline
    from app.workers.pipeline import run_pipeline
    run_pipeline.delay(str(repo_id), str(job_id), source_url)

    return ImportResponse(repository_id=repo_id, job_id=job_id, status="pending")


@router.get("", response_model=dict)
async def list_repositories(user_id: CurrentUserId):
    """List all repositories owned by the current user (FR-10.2)."""
    async with get_db_context() as db:
        result = await db.execute(
            select(Repository)
            .where(Repository.owner_user_id == user_id)
            .order_by(Repository.created_at.desc())
        )
        repos = result.scalars().all()

    return {
        "repositories": [RepositoryOut.model_validate(r) for r in repos]
    }


@router.get("/{repository_id}", response_model=RepositoryOut)
async def get_repository(repository_id: uuid.UUID, user_id: CurrentUserId):
    """Get full repository detail (FR-10.1)."""
    async with get_db_context() as db:
        repo = await _verify_repo_access(db, repository_id, user_id)
    return RepositoryOut.model_validate(repo)


@router.delete("/{repository_id}", status_code=204)
async def delete_repository(repository_id: uuid.UUID, user_id: CurrentUserId):
    """Delete repository and ALL derived data (NFR-13, FR-2.9)."""
    async with get_db_context() as db:
        repo = await _verify_repo_access(db, repository_id, user_id)
        await db.delete(repo)
    return None


@router.post("/{repository_id}/reindex", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def reindex_repository(repository_id: uuid.UUID, user_id: CurrentUserId):
    """Re-trigger the processing pipeline (FR-2.8)."""
    async with get_db_context() as db:
        repo = await _verify_repo_access(db, repository_id, user_id)
        repo.status = "pending"

        job = IndexingJob(
            repository_id=repo.id,
            stage="pending",
            progress_pct=0,
        )
        db.add(job)
        await db.flush()
        job_id = job.id
        source_url = repo.source_url

    from app.workers.pipeline import run_pipeline
    run_pipeline.delay(str(repository_id), str(job_id), source_url)

    return {"job_id": str(job_id)}


# ── Analysis Endpoints ────────────────────────────────────────────────────────

@router.get("/{repository_id}/health", response_model=dict)
async def get_health_report(repository_id: uuid.UUID, user_id: CurrentUserId):
    """Get the latest health report for a repository (FR-9)."""
    async with get_db_context() as db:
        await _verify_repo_access(db, repository_id, user_id)

        # Get latest health report
        hr_result = await db.execute(
            select(HealthReportModel)
            .where(HealthReportModel.repository_id == repository_id)
            .order_by(HealthReportModel.generated_at.desc())
            .limit(1)
        )
        report = hr_result.scalar_one_or_none()

        if not report:
            raise HTTPException(
                status_code=404,
                detail="Health report not yet generated. The repository may still be indexing."
            )

        from app.workers.pipeline import _is_non_production_path
        SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

        # Get top issues from static analysis, sorted by severity hierarchy
        issues_result = await db.execute(
            select(StaticAnalysisResult)
            .where(StaticAnalysisResult.repository_id == repository_id)
            .limit(100)
        )
        raw_issues = issues_result.scalars().all()
        sorted_issues = sorted(raw_issues, key=lambda x: SEV_ORDER.get((x.severity or "").lower(), 5))[:25]

        top_issues = []
        for issue in sorted_issues:
            # Get the file path
            file_path = ""
            if issue.file_id:
                file_result = await db.execute(select(File).where(File.id == issue.file_id))
                f = file_result.scalar_one_or_none()
                if f:
                    file_path = f.path

            top_issues.append({
                "severity": issue.severity,
                "tool": issue.tool,
                "rule_id": issue.rule_id,
                "message": issue.message,
                "file_path": file_path,
                "line": issue.line or 0,
                "is_non_production": _is_non_production_path(file_path) if file_path else False,
            })

    return {
        "overall_score": report.overall_score,
        "complexity_score": report.complexity_score,
        "security_score": report.security_score,
        "duplication_score": report.duplication_score,
        "code_quality_score": report.duplication_score,  # Alias for duplication_score representing code quality
        "dependency_score": report.dependency_score,
        "metrics_json": report.metrics_json,
        "top_issues": top_issues,
        "generated_at": report.generated_at.isoformat(),
    }


@router.get("/{repository_id}/architecture", response_model=dict)
async def get_architecture(repository_id: uuid.UUID, user_id: CurrentUserId):
    """Get the architecture view: components and relationships (FR-6).
    Constructs a component dependency graph from real graph_edges (imports/calls).
    """
    async with get_db_context() as db:
        await _verify_repo_access(db, repository_id, user_id)

        # 1. Fetch real graph edges for this repo (imports, calls, depends_on, extends)
        edges_result = await db.execute(
            select(GraphEdge)
            .where(
                GraphEdge.repository_id == repository_id,
                GraphEdge.edge_type.in_(["imports", "calls", "depends_on", "extends"])
            )
            .limit(5000)
        )
        edges = edges_result.scalars().all()

        # 2. Fetch all nodes involved in these edges
        node_ids = set()
        for e in edges:
            node_ids.add(e.source_node_id)
            node_ids.add(e.target_node_id)

        nodes_by_id: dict[uuid.UUID, GraphNode] = {}
        if node_ids:
            nodes_result = await db.execute(
                select(GraphNode).where(GraphNode.id.in_(list(node_ids)[:3000]))
            )
            for n in nodes_result.scalars().all():
                nodes_by_id[n.id] = n

        # Also fetch files in the repo to map file_id -> path
        files_result = await db.execute(
            select(File).where(File.repository_id == repository_id).limit(1000)
        )
        files = files_result.scalars().all()
        file_map: dict[uuid.UUID, str] = {f.id: f.path for f in files}

        def get_node_file(node: GraphNode) -> str:
            """Map a node to its file path."""
            if node.file_id and node.file_id in file_map:
                return file_map[node.file_id]
            if "::" in node.qualified_name:
                return node.qualified_name.split("::")[0]
            return node.qualified_name

        def file_to_package(fpath: str, depth: int) -> str:
            """Group a file path into a package at the given directory depth.
            depth=1: 'pkg/sub/mod.py' -> 'pkg'
            depth=2: 'pkg/sub/mod.py' -> 'pkg/sub'
            Files at root: 'mod.py' -> 'mod.py' (keep as-is)
            """
            parts = fpath.split("/")
            if len(parts) <= depth:
                return fpath  # root file or already shallow enough
            return "/".join(parts[:depth])

        # 3. Build per-file edge map first
        file_edge_counts: dict[tuple[str, str, str], int] = {}
        for edge in edges:
            src_node = nodes_by_id.get(edge.source_node_id)
            tgt_node = nodes_by_id.get(edge.target_node_id)
            if not src_node or not tgt_node:
                continue

            if src_node.node_type == "external":
                src_key = f"ext:{src_node.name.split('.')[0]}"
            else:
                src_key = get_node_file(src_node)

            if tgt_node.node_type == "external":
                tgt_key = f"ext:{tgt_node.name.split('.')[0]}"
            else:
                tgt_key = get_node_file(tgt_node)

            if src_key and tgt_key and src_key != tgt_key:
                key = (src_key, tgt_key, edge.edge_type)
                file_edge_counts[key] = file_edge_counts.get(key, 0) + 1

        # 4. Determine clustering depth adaptively
        unique_files = set()
        for (s, t, _) in file_edge_counts:
            if not s.startswith("ext:"):
                unique_files.add(s)
            if not t.startswith("ext:"):
                unique_files.add(t)

        # Pick grouping depth: keep file-level if <=15 files, else package-level
        if len(unique_files) <= 15:
            cluster_depth = 0  # no clustering, keep file-level
        elif len(unique_files) <= 40:
            cluster_depth = 2  # group by 2nd-level directory
        else:
            cluster_depth = 1  # group by top-level directory

        def to_component_id(fpath: str) -> str:
            if fpath.startswith("ext:"):
                return fpath
            if cluster_depth == 0:
                return fpath
            return file_to_package(fpath, cluster_depth)

        # 5. Aggregate edges at the chosen clustering level
        comp_edge_counts: dict[tuple[str, str, str], int] = {}
        comp_files_map: dict[str, set[str]] = {}

        # Seed comp_files_map with all known files
        for f in files:
            cid = to_component_id(f.path)
            comp_files_map.setdefault(cid, set()).add(f.path)

        for (s, t, etype), cnt in file_edge_counts.items():
            cs = to_component_id(s)
            ct = to_component_id(t)
            if cs != ct:
                ckey = (cs, ct, etype)
                comp_edge_counts[ckey] = comp_edge_counts.get(ckey, 0) + cnt
            # Track files/externals in components
            if s.startswith("ext:"):
                comp_files_map.setdefault(cs, set())  # external has no files
            else:
                comp_files_map.setdefault(cs, set()).add(s)
            if t.startswith("ext:"):
                comp_files_map.setdefault(ct, set())  # external has no files
            else:
                comp_files_map.setdefault(ct, set()).add(t)

        # 6. Merge edge types per component pair (imports+calls -> strongest type)
        merged_edges: dict[tuple[str, str], dict] = {}
        for (s, t, etype), cnt in comp_edge_counts.items():
            pair = (s, t)
            if pair not in merged_edges:
                merged_edges[pair] = {"from": s, "to": t, "type": etype, "weight": cnt}
            else:
                merged_edges[pair]["weight"] += cnt
                # prefer "calls" > "imports" > others as the display type
                type_rank = {"calls": 3, "extends": 2, "depends_on": 1, "imports": 0}
                if type_rank.get(etype, 0) > type_rank.get(merged_edges[pair]["type"], 0):
                    merged_edges[pair]["type"] = etype

        # 7. Sort by weight and cap
        sorted_rels = sorted(merged_edges.values(), key=lambda x: x["weight"], reverse=True)
        relationships = sorted_rels[:80]

        connected_ids = set()
        for r in relationships:
            connected_ids.add(r["from"])
            connected_ids.add(r["to"])

        # 8. Limit external deps to the most-connected (top 8) to avoid clutter
        ext_edge_weight: dict[str, int] = {}
        for r in relationships:
            for cid in (r["from"], r["to"]):
                if cid.startswith("ext:"):
                    ext_edge_weight[cid] = ext_edge_weight.get(cid, 0) + r.get("weight", 1)
        top_externals = set(
            k for k, _ in sorted(ext_edge_weight.items(), key=lambda x: x[1], reverse=True)[:8]
        )
        # Remove edges referencing pruned externals
        relationships = [
            r for r in relationships
            if not (r["from"].startswith("ext:") and r["from"] not in top_externals)
            and not (r["to"].startswith("ext:") and r["to"] not in top_externals)
        ]

        # Rebuild connected set after pruning
        connected_ids = set()
        for r in relationships:
            connected_ids.add(r["from"])
            connected_ids.add(r["to"])

        # 9. Build component list
        components = []
        for cid in sorted(comp_files_map.keys()):
            if cid.startswith("ext:") and cid not in top_externals:
                continue  # skip low-weight externals
            if not connected_ids or cid in connected_ids:
                flist = sorted(list(comp_files_map[cid]))
                is_external = cid.startswith("ext:")
                components.append({
                    "id": cid,
                    "label": cid.replace("ext:", "📦 ") if is_external else cid,
                    "files": flist[:10],
                    "type": "external" if is_external else "internal",
                    "fileCount": len(flist),
                })
            if len(components) >= 40:
                break

    return {
        "components": components,
        "relationships": relationships,
    }


@router.post("/{repository_id}/trace", response_model=dict)
async def trace_feature(
    repository_id: uuid.UUID,
    body: dict,
    user_id: CurrentUserId,
):
    """
    Trace a feature or user flow through the codebase (FR-8).
    Uses embeddings to find the most relevant entry-point node,
    then traverses real graph_edges (calls, imports) to construct the execution path.
    """
    description = body.get("description", "").strip()

    async with get_db_context() as db:
        await _verify_repo_access(db, repository_id, user_id)

        if not description:
            return {"steps": [], "confidence": "low", "completeness_pct": 0}

        # 1. Fetch entry point via pgvector embeddings similarity (matching chat._fetch_context_nodes)
        entry_nodes = []
        has_embeddings = False
        emb_check = await db.execute(
            select(Embedding.id).where(Embedding.repository_id == repository_id).limit(1)
        )
        has_embeddings = emb_check.scalar_one_or_none() is not None

        if has_embeddings:
            try:
                from app.embeddings import embed_text
                query_vec = embed_text(description)

                rows = await db.execute(
                    sa_text("""
                        SELECT
                            gn.id            AS id,
                            gn.name          AS name,
                            gn.qualified_name AS qualified_name,
                            gn.node_type     AS node_type,
                            gn.file_id       AS file_id,
                            (1 - (e.vector <=> CAST(:qvec AS vector))) AS score
                        FROM embeddings e
                        JOIN graph_nodes gn ON gn.id = e.node_id
                        WHERE e.repository_id = :repo_id
                          AND gn.node_type IN ('function', 'class', 'method', 'route')
                        ORDER BY e.vector <=> CAST(:qvec AS vector)
                        LIMIT 5
                    """),
                    {
                        "repo_id": str(repository_id),
                        "qvec": "[" + ",".join(str(x) for x in query_vec) + "]",
                    },
                )
                entry_nodes = [r for r in rows if float(r.score) >= 0.25]
            except Exception as exc:
                logger.warning("Vector search for trace entry-point failed", error=str(exc))

        # Keyword fallback for entry point if vector search returned nothing
        if not entry_nodes:
            keywords = set(kw.lower() for kw in description.split() if len(kw) > 2)
            nodes_result = await db.execute(
                select(GraphNode)
                .where(
                    GraphNode.repository_id == repository_id,
                    GraphNode.node_type.in_(["function", "class", "method", "route"]),
                )
                .limit(300)
            )
            raw_nodes = nodes_result.scalars().all()
            scored = []
            for n in raw_nodes:
                text_content = f"{n.name} {n.docstring or ''} {n.qualified_name}".lower()
                sc = sum(1 for kw in keywords if kw in text_content)
                if sc > 0:
                    scored.append((sc, n))
            scored.sort(key=lambda x: x[0], reverse=True)
            entry_nodes = [n for _, n in scored[:5]]

        if not entry_nodes:
            return {"steps": [], "confidence": "low", "completeness_pct": 0}

        # 2. Call-graph traversal using real graph_edges
        files_result = await db.execute(
            select(File).where(File.repository_id == repository_id)
        )
        file_map: dict[uuid.UUID, str] = {f.id: f.path for f in files_result.scalars().all()}

        primary_entry = entry_nodes[0]
        visited_ids: set[uuid.UUID] = {primary_entry.id}
        execution_chain: list[dict] = []

        def resolve_file_path(node_file_id: Optional[uuid.UUID], qname: str) -> str:
            if node_file_id and node_file_id in file_map:
                return file_map[node_file_id]
            if "::" in qname:
                return qname.split("::")[0]
            return qname

        def infer_role(name: str, qname: str, node_type: str, step_idx: int) -> str:
            if step_idx == 0:
                return "entry_point"
            lower = f"{name} {qname}".lower()
            if any(term in lower for term in ("route", "endpoint", "view", "controller", "handler", "api")):
                return "handler"
            if any(term in lower for term in ("db", "model", "query", "repo", "store", "table", "schema", "sql", "crud")):
                return "data_access"
            if any(term in lower for term in ("service", "client", "core", "logic", "auth", "process", "engine", "session")):
                return "business_logic"
            if step_idx == 1:
                return "handler"
            if node_type in ("function", "method"):
                return "business_logic"
            return "utility"

        execution_chain.append({
            "node_id": str(primary_entry.id),
            "name": primary_entry.name,
            "file_path": resolve_file_path(primary_entry.file_id, primary_entry.qualified_name),
            "role": "entry_point",
        })

        current_layer = [primary_entry.id]
        max_steps = 8

        for _ in range(3):  # up to 3 hops
            if len(execution_chain) >= max_steps or not current_layer:
                break

            edges_result = await db.execute(
                select(GraphEdge)
                .where(
                    GraphEdge.repository_id == repository_id,
                    GraphEdge.source_node_id.in_(current_layer),
                    GraphEdge.edge_type.in_(["calls", "imports", "extends"]),
                )
                .order_by(
                    case((GraphEdge.edge_type == "calls", 1), else_=2),
                    GraphEdge.confidence.desc()
                )
                .limit(20)
            )
            hop_edges = edges_result.scalars().all()
            next_layer = []

            target_ids = [e.target_node_id for e in hop_edges if e.target_node_id not in visited_ids]
            if target_ids:
                nodes_res = await db.execute(
                    select(GraphNode).where(GraphNode.id.in_(target_ids))
                )
                hop_nodes = {n.id: n for n in nodes_res.scalars().all()}

                for e in hop_edges:
                    tid = e.target_node_id
                    if tid in hop_nodes and tid not in visited_ids:
                        visited_ids.add(tid)
                        tnode = hop_nodes[tid]
                        if tnode.node_type == "external" and len(execution_chain) >= 4:
                            continue
                        next_layer.append(tid)
                        fpath = resolve_file_path(tnode.file_id, tnode.qualified_name)
                        role = infer_role(tnode.name, tnode.qualified_name, tnode.node_type, len(execution_chain))
                        execution_chain.append({
                            "node_id": str(tnode.id),
                            "name": tnode.name,
                            "file_path": fpath,
                            "role": role,
                        })
                        if len(execution_chain) >= max_steps:
                            break

            current_layer = next_layer

        if len(execution_chain) < 3 and len(entry_nodes) > 1:
            for extra_entry in entry_nodes[1:]:
                if extra_entry.id not in visited_ids:
                    visited_ids.add(extra_entry.id)
                    fpath = resolve_file_path(extra_entry.file_id, extra_entry.qualified_name)
                    role = infer_role(extra_entry.name, extra_entry.qualified_name, extra_entry.node_type, len(execution_chain))
                    execution_chain.append({
                        "node_id": str(extra_entry.id),
                        "name": extra_entry.name,
                        "file_path": fpath,
                        "role": role,
                    })
                    if len(execution_chain) >= 5:
                        break

        steps = [
            {"order": i + 1, **step_data}
            for i, step_data in enumerate(execution_chain)
        ]

        completeness = min(100, len(steps) * 15)
        confidence = "high" if len(steps) >= 4 and has_embeddings else ("medium" if len(steps) >= 2 else "low")

        return {
            "steps": steps,
            "confidence": confidence,
            "completeness_pct": completeness,
        }


@router.get("/{repository_id}/search", response_model=dict)
async def semantic_search(
    repository_id: uuid.UUID,
    q: str = Query(..., description="Search query"),
    user_id: CurrentUserId = None,
):
    """
    Semantic code search using pgvector cosine similarity (FR-5).

    Embeds the query with all-MiniLM-L6-v2 and finds the nearest graph
    nodes by cosine distance in the embeddings table.  Falls back to
    keyword matching if no embeddings have been generated yet (i.e. the
    repo is still indexing or embed_task hasn't run).
    """
    async with get_db_context() as db:
        await _verify_repo_access(db, repository_id, user_id)

        results = None  # set by vector path; None triggers keyword fallback

        # ── Try pgvector similarity search first ──────────────────────────
        emb_count_result = await db.execute(
            select(Embedding.id)
            .where(Embedding.repository_id == repository_id)
            .limit(1)
        )
        has_embeddings = emb_count_result.scalar_one_or_none() is not None

        if has_embeddings:
            try:
                from app.embeddings import embed_text
                query_vec = embed_text(q)  # list[float], length 384

                # pgvector operator <=> = cosine distance (0 = identical, 2 = opposite)
                rows = await db.execute(
                    sa_text("""
                        SELECT
                            gn.id            AS node_id,
                            gn.name          AS name,
                            gn.qualified_name AS qualified_name,
                            gn.node_type     AS node_type,
                            gn.start_line    AS start_line,
                            (1 - (e.vector <=> CAST(:qvec AS vector))) AS score
                        FROM embeddings e
                        JOIN graph_nodes gn ON gn.id = e.node_id
                        WHERE e.repository_id = :repo_id
                        ORDER BY e.vector <=> CAST(:qvec AS vector)
                        LIMIT 20
                    """),
                    {
                        "repo_id": str(repository_id),
                        "qvec": "[" + ",".join(str(x) for x in query_vec) + "]",
                    },
                )
                results = [
                    {
                        "node_id": str(row.node_id),
                        "name": row.name,
                        "file_path": row.qualified_name.split("::")[0] if "::" in row.qualified_name else "",
                        "node_type": row.node_type,
                        "line": row.start_line or 0,
                        "score": round(float(row.score), 4),
                        "method": "vector",
                    }
                    for row in rows
                ]
            except Exception as exc:
                logger.warning(
                    "Vector search failed, falling back to keyword",
                    repository_id=str(repository_id),
                    query=q,
                    error=str(exc),
                )
                results = None  # force keyword fallback below

        if results is None:
            # ── Keyword fallback (pre-embed, vector failure, or small repo) ─
            nodes_result = await db.execute(
                select(GraphNode)
                .where(GraphNode.repository_id == repository_id)
                .limit(500)
            )
            nodes = nodes_result.scalars().all()

            keywords = set(kw.lower() for kw in q.split() if len(kw) > 2)
            scored: list[tuple[float, GraphNode]] = []
            for node in nodes:
                text = f"{node.name} {node.docstring or ''} {node.qualified_name} {node.signature or ''}".lower()
                score = sum(1.0 for kw in keywords if kw in text) / max(len(keywords), 1)
                if score > 0:
                    scored.append((score, node))

            scored.sort(key=lambda x: x[0], reverse=True)
            results = [
                {
                    "node_id": str(node.id),
                    "name": node.name,
                    "file_path": node.qualified_name.split("::")[0] if "::" in node.qualified_name else "",
                    "node_type": node.node_type,
                    "line": node.start_line or 0,
                    "score": round(score, 3),
                    "method": "keyword",
                }
                for score, node in scored[:20]
            ]

    return {"results": results}


@router.get("/{repository_id}/graph", response_model=dict)
async def get_graph(
    repository_id: uuid.UUID,
    max_nodes: int = Query(200, ge=10, le=500),
    user_id: CurrentUserId = None,
):
    """Get the code knowledge graph (FR-4)."""
    async with get_db_context() as db:
        await _verify_repo_access(db, repository_id, user_id)

        nodes_result = await db.execute(
            select(GraphNode)
            .where(GraphNode.repository_id == repository_id)
            .limit(max_nodes)
        )
        nodes = nodes_result.scalars().all()

        node_ids = {node.id for node in nodes}

        edges_result = await db.execute(
            select(GraphEdge)
            .where(GraphEdge.repository_id == repository_id)
            .limit(max_nodes * 3)
        )
        edges = edges_result.scalars().all()

    return {
        "nodes": [
            {
                "id": str(n.id),
                "name": n.name,
                "node_type": n.node_type,
                "qualified_name": n.qualified_name,
                "start_line": n.start_line,
                "end_line": n.end_line,
                "signature": n.signature,
                "docstring": n.docstring,
            }
            for n in nodes
        ],
        "edges": [
            {
                "source": str(e.source_node_id),
                "target": str(e.target_node_id),
                "edge_type": e.edge_type,
            }
            for e in edges
            if e.source_node_id in node_ids and e.target_node_id in node_ids
        ],
    }
