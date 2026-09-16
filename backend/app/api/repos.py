"""
DevLens AI — Repository API Router
CRUD for repositories + job status polling + analysis endpoints.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import select, desc

from app.auth.dependencies import CurrentUserId
from app.database import get_db_context
from app.models import (
    IndexingJob, Repository, HealthReport as HealthReportModel,
    GraphNode, GraphEdge, StaticAnalysisResult, File
)

router = APIRouter(prefix="/repositories", tags=["repositories"])


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

        # Get top issues from static analysis
        issues_result = await db.execute(
            select(StaticAnalysisResult)
            .where(StaticAnalysisResult.repository_id == repository_id)
            .order_by(StaticAnalysisResult.severity)
            .limit(20)
        )
        issues = issues_result.scalars().all()

        top_issues = []
        for issue in issues:
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
                "message": issue.message,
                "file_path": file_path,
                "line": issue.line or 0,
            })

    return {
        "overall_score": report.overall_score,
        "complexity_score": report.complexity_score,
        "security_score": report.security_score,
        "duplication_score": report.duplication_score,
        "dependency_score": report.dependency_score,
        "top_issues": top_issues,
        "generated_at": report.generated_at.isoformat(),
    }


@router.get("/{repository_id}/architecture", response_model=dict)
async def get_architecture(repository_id: uuid.UUID, user_id: CurrentUserId):
    """Get the architecture view: components and relationships (FR-6)."""
    async with get_db_context() as db:
        await _verify_repo_access(db, repository_id, user_id)

        # Get files grouped by top-level directory (= components)
        files_result = await db.execute(
            select(File).where(File.repository_id == repository_id).limit(500)
        )
        files = files_result.scalars().all()

        # Group files into components by their top-level directory
        component_map: dict[str, list[str]] = {}
        for f in files:
            parts = f.path.split("/")
            component = parts[0] if len(parts) > 1 else "root"
            if component not in component_map:
                component_map[component] = []
            component_map[component].append(f.path)

        components = [
            {"id": comp_id, "label": comp_id, "files": file_list[:10]}
            for comp_id, file_list in sorted(component_map.items())
        ]

        # Build relationships from graph edges (via nodes' file components)
        edges_result = await db.execute(
            select(GraphEdge).where(GraphEdge.repository_id == repository_id).limit(1000)
        )
        edges = edges_result.scalars().all()

        # Map node_id → component
        node_result = await db.execute(
            select(GraphNode).where(GraphNode.repository_id == repository_id).limit(1000)
        )
        nodes = node_result.scalars().all()

        node_to_comp: dict[str, str] = {}
        for node in nodes:
            parts = node.qualified_name.split("/")
            comp = parts[0] if len(parts) > 1 else "root"
            node_to_comp[str(node.id)] = comp

        # Aggregate component-level relationships
        rel_set: set[tuple[str, str, str]] = set()
        for edge in edges:
            src_comp = node_to_comp.get(str(edge.source_node_id))
            tgt_comp = node_to_comp.get(str(edge.target_node_id))
            if src_comp and tgt_comp and src_comp != tgt_comp:
                rel_set.add((src_comp, tgt_comp, edge.edge_type))

        relationships = [
            {"from": r[0], "to": r[1], "type": r[2]}
            for r in list(rel_set)[:50]
        ]

    return {
        "components": components[:20],
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
    Uses keyword matching on graph nodes to build an execution path.
    """
    description = body.get("description", "")

    async with get_db_context() as db:
        await _verify_repo_access(db, repository_id, user_id)

        # Fetch nodes relevant to the description
        nodes_result = await db.execute(
            select(GraphNode)
            .where(
                GraphNode.repository_id == repository_id,
                GraphNode.node_type.in_(["function", "class", "method", "route"]),
            )
            .limit(300)
        )
        nodes = nodes_result.scalars().all()

        # Score nodes by keyword relevance
        keywords = set(kw.lower() for kw in description.split() if len(kw) > 2)
        scored: list[tuple[int, GraphNode]] = []
        for node in nodes:
            text = f"{node.name} {node.docstring or ''} {node.qualified_name} {node.signature or ''}".lower()
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scored.append((score, node))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_nodes = scored[:10]

        steps = [
            {
                "order": i + 1,
                "node_id": str(node.id),
                "name": node.name,
                "file_path": node.qualified_name.split("::")[0] if "::" in node.qualified_name else "",
                "role": node.node_type,
            }
            for i, (_, node) in enumerate(top_nodes)
        ]

    completeness = min(100, len(steps) * 10)
    confidence = "high" if completeness >= 70 else "medium" if completeness >= 40 else "low"

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
    """Search code nodes semantically using keyword matching (FR-5)."""
    async with get_db_context() as db:
        await _verify_repo_access(db, repository_id, user_id)

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
                "line": node.start_line or 0,
                "score": round(score, 3),
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
