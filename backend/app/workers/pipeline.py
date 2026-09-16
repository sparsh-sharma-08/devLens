"""
DevLens AI — Processing Pipeline
Celery task chain: clone → detect_language → parse → build_graph → embed → analyze → report

Each task:
  - Updates the indexing_job stage + progress_pct
  - Updates the repository status
  - Is independently retryable (NFR-4)
  - Skips individual failures without halting the overall pipeline (NFR-4)

Sprint 1-2: clone + detect_language implemented.
Sprint 3:   parse implemented — tree-sitter AST walker for Python.
Sprint 4-6: remaining tasks will be added.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
import hashlib
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog
from celery import chain

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

# Pipeline stage → progress percentage milestones
STAGE_PROGRESS = {
    "cloning": 5,
    "detecting_language": 15,
    "parsing": 30,
    "building_graph": 50,
    "embedding": 70,
    "static_analysis": 85,
    "report_generation": 95,
    "done": 100,
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _run_async(coro):
    """Run an async coroutine from synchronous Celery task context."""
    return asyncio.get_event_loop().run_until_complete(coro)


async def _update_job(job_id: str, stage: str, progress_pct: int, error: str | None = None):
    """Update indexing_job stage and progress in the DB."""
    from app.database import get_db_context
    from app.models import IndexingJob, Repository
    from sqlalchemy import select

    async with get_db_context() as db:
        result = await db.execute(select(IndexingJob).where(IndexingJob.id == uuid.UUID(job_id)))
        job = result.scalar_one_or_none()
        if job:
            job.stage = stage
            job.progress_pct = progress_pct
            job.error_message = error
            if stage in ("done", "failed"):
                job.completed_at = datetime.now(timezone.utc)

        # Also update the repository status
        repo_result = await db.execute(
            select(Repository).where(Repository.id == job.repository_id)
        )
        repo = repo_result.scalar_one_or_none()
        if repo:
            if stage == "done":
                repo.status = "ready"
                repo.last_indexed_at = datetime.now(timezone.utc)
            elif stage == "failed":
                repo.status = "failed"
            else:
                repo.status = "indexing"


# ─────────────────────────────────────────────────────────────────────────────
# Task: Clone Repository
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def clone_task(self, repo_id: str, job_id: str, source_url: str) -> dict:
    """
    Stage 1: Shallow clone the repository into an isolated workspace.
    Enforces the size limit (FR-2.4).
    """
    log = logger.bind(task="clone", repo_id=repo_id, job_id=job_id)
    log.info("Starting clone stage")

    try:
        _run_async(_update_job(job_id, "cloning", STAGE_PROGRESS["cloning"]))

        from app.config import get_settings
        settings = get_settings()

        workspace_dir = Path(settings.clone_workspace_dir) / repo_id
        workspace_dir.mkdir(parents=True, exist_ok=True)

        import git
        log.info("Cloning repository", url=source_url, dest=str(workspace_dir))
        repo = git.Repo.clone_from(
            source_url,
            str(workspace_dir),
            depth=1,        # Shallow clone — only latest commit (much faster)
            no_tags=True,
        )

        # Count lines of code (rough estimate: count non-empty lines in text files)
        total_loc = _count_loc(workspace_dir)
        log.info("Clone complete", loc=total_loc)

        if total_loc > settings.max_repo_loc:
            shutil.rmtree(workspace_dir, ignore_errors=True)
            _run_async(_update_job(job_id, "failed", 0, f"Repository exceeds {settings.max_repo_loc} LOC limit"))
            raise ValueError(f"Repository exceeds LOC limit: {total_loc} > {settings.max_repo_loc}")

        return {"repo_id": repo_id, "job_id": job_id, "workspace": str(workspace_dir), "loc": total_loc}

    except Exception as exc:
        log.error("Clone stage failed", error=str(exc))
        _run_async(_update_job(job_id, "failed", 0, str(exc)))
        raise self.retry(exc=exc)


def _count_loc(workspace: Path) -> int:
    """Count approximate lines of code, skipping binary/vendor directories."""
    SKIP_DIRS = {
        "node_modules", ".git", "venv", ".venv", "__pycache__",
        "vendor", "dist", "build", ".next", "coverage",
    }
    total = 0
    try:
        for f in workspace.rglob("*"):
            if f.is_file() and not any(part in SKIP_DIRS for part in f.parts):
                try:
                    with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                        total += sum(1 for line in fh if line.strip())
                except Exception:
                    pass
    except Exception:
        pass
    return total


# ─────────────────────────────────────────────────────────────────────────────
# Task: Detect Language
# ─────────────────────────────────────────────────────────────────────────────

EXTENSION_TO_LANGUAGE = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".cpp": "C++",
    ".c": "C",
    ".cs": "C#",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
}

SKIP_DIRS = {
    "node_modules", ".git", "venv", ".venv", "__pycache__",
    "vendor", "dist", "build", ".next", "coverage",
}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def detect_language_task(self, prev_result: dict) -> dict:
    """
    Stage 2: Detect primary language(s) by file extension frequency.
    Updates the repository record with language metadata.
    """
    repo_id = prev_result["repo_id"]
    job_id = prev_result["job_id"]
    workspace = prev_result["workspace"]

    log = logger.bind(task="detect_language", repo_id=repo_id)
    log.info("Starting language detection")

    try:
        _run_async(_update_job(job_id, "detecting_language", STAGE_PROGRESS["detecting_language"]))

        workspace_path = Path(workspace)
        lang_counts: dict[str, int] = {}

        for f in workspace_path.rglob("*"):
            if f.is_file() and not any(part in SKIP_DIRS for part in f.parts):
                lang = EXTENSION_TO_LANGUAGE.get(f.suffix.lower())
                if lang:
                    lang_counts[lang] = lang_counts.get(lang, 0) + 1

        if not lang_counts:
            lang_counts = {"Unknown": 1}

        total = sum(lang_counts.values())
        language_pcts = {lang: round(count / total * 100) for lang, count in lang_counts.items()}
        primary_language = max(lang_counts, key=lang_counts.get)

        log.info("Language detection complete", primary=primary_language, distribution=language_pcts)

        # Update repository record
        from app.database import get_db_context
        from app.models import Repository
        from sqlalchemy import select

        async def _update_repo():
            async with get_db_context() as db:
                result = await db.execute(select(Repository).where(Repository.id == uuid.UUID(repo_id)))
                repo = result.scalar_one_or_none()
                if repo:
                    repo.primary_language = primary_language
                    repo.languages = language_pcts

        _run_async(_update_repo())

        return {
            **prev_result,
            "primary_language": primary_language,
            "languages": language_pcts,
        }

    except Exception as exc:
        log.error("Language detection failed", error=str(exc))
        # Non-fatal — continue pipeline with unknown language
        return {**prev_result, "primary_language": "Unknown", "languages": {}}


# ─────────────────────────────────────────────────────────────────────────────
# Parse helpers
# ─────────────────────────────────────────────────────────────────────────────

# Directories skipped during the parse walk (mirrors _count_loc / detect_language)
_PARSE_SKIP_DIRS: frozenset[str] = frozenset({
    ".git", "venv", ".venv", "__pycache__", "node_modules",
    "migrations", "vendor", "dist", "build", ".next", "coverage",
})

# How many files to accumulate before flushing to the DB
_PARSE_BATCH_SIZE = 200


def _compute_sha(path: Path) -> str:
    """Return a git blob-compatible SHA-1 for the file at *path*.

    Git computes: SHA1("blob " + str(byte_len) + "\0" + file_bytes)
    This lets Stage 4 detect unchanged files on re-index without shelling out.
    """
    raw = path.read_bytes()
    header = f"blob {len(raw)}\0".encode()
    return hashlib.sha1(header + raw).hexdigest()  # noqa: S324 (SHA1 is intentional here)


def _extract_docstring(body_node) -> str | None:
    """Return the text of the first string-literal statement in a class/function body.

    In tree-sitter's Python grammar the body of a function or class is an
    ``block`` node whose first ``expression_statement`` child may contain a
    ``string`` node — that is the docstring.
    """
    if body_node is None:
        return None
    # body_node is a ``block`` (indented suite)
    for child in body_node.children:
        if child.type == "expression_statement":
            for sub in child.children:
                if sub.type in ("string", "concatenated_string"):
                    # Strip surrounding quotes; tree-sitter preserves the raw literal
                    raw = sub.text
                    if raw is None:
                        return None
                    text = raw.decode("utf-8", errors="replace")
                    # Remove triple-quote wrappers ("""…""", '''…''', "…", '…')
                    for q in ('"""', "'''", '"', "'"):
                        if text.startswith(q) and text.endswith(q) and len(text) > 2 * len(q):
                            return text[len(q): -len(q)].strip()
                    return text.strip()
            break  # only check the first statement
    return None


def _build_signature(func_node, src_bytes: bytes) -> str:
    """Build a complete, normalised function signature from tree-sitter AST fields.

    Uses the named fields ``name``, ``parameters``, and ``return_type`` rather
    than slicing on the first physical line, so multi-line signatures (many params,
    type annotations, trailing commas) are captured in full without truncation.

    Example output:  ``def fetch(url: str, timeout: int = 30) -> Response``
    """
    is_async = func_node.type == "async_function_definition"
    prefix = "async def" if is_async else "def"

    name_node   = func_node.child_by_field_name("name")
    params_node = func_node.child_by_field_name("parameters")
    return_node = func_node.child_by_field_name("return_type")

    name = (
        name_node.text.decode("utf-8", errors="replace")
        if (name_node and name_node.text) else ""
    )
    # Collapse interior whitespace so multi-line param lists become a single line
    params_raw = (
        params_node.text.decode("utf-8", errors="replace")
        if (params_node and params_node.text) else "()"
    )
    params = " ".join(params_raw.split())

    sig = f"{prefix} {name}{params}"
    if return_node and return_node.text:
        ret = return_node.text.decode("utf-8", errors="replace").strip()
        sig = f"{sig} -> {ret}"
    return sig


def _walk_python_ast(
    tree,
    src_bytes: bytes,
    rel_path: str,
) -> list[dict]:
    """Walk a tree-sitter parse tree and return a list of entity dicts.

    Each dict has keys:
        node_type       str   – "function" | "method" | "class" | "import"
        name            str   – simple (unqualified) name
        qualified_name  str   – ``<rel_path>::<QualifiedName>``
        start_line      int   – 1-based
        end_line        int   – 1-based
        signature       str | None
        docstring       str | None

    Qualified-name convention (PEP 3155, stable, collision-free):
        • Module-level function : ``path/file.py::my_func``
        • Class                 : ``path/file.py::MyClass``
        • Method                : ``path/file.py::MyClass.my_method``
        • Nested function       : ``path/file.py::outer.<locals>.inner``
        • Class in function     : ``path/file.py::outer.<locals>.LocalClass``
        • Method in local class : ``path/file.py::outer.<locals>.LocalClass.my_method``
        • Import                : ``path/file.py::import:<module_path>``
    """
    entities: list[dict] = []
    seen_qnames: dict[str, int] = {}

    def _get_unique_qname(base_qname: str) -> str:
        """Ensure qualified_name is unique within the file (handles overloads, property setters, redefinitions)."""
        count = seen_qnames.get(base_qname, 0)
        seen_qnames[base_qname] = count + 1
        if count == 0:
            return base_qname
        return f"{base_qname}#{count + 1}"

    def _visit(node, scope_prefix: str, in_func: bool) -> None:
        """Recursive DFS visitor tracking PEP 3155 scope."""
        ntype = node.type

        # ── class_definition ───────────────────────────────────────────────
        if ntype == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                return
            class_name = name_node.text.decode("utf-8", errors="replace") if name_node.text else ""
            if not scope_prefix:
                qualname = class_name
            elif in_func:
                qualname = f"{scope_prefix}.<locals>.{class_name}"
            else:
                qualname = f"{scope_prefix}.{class_name}"

            base_qname = f"{rel_path}::{qualname}"
            qname = _get_unique_qname(base_qname)
            body_node = node.child_by_field_name("body")
            entities.append({
                "node_type": "class",
                "name": class_name,
                "qualified_name": qname,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "signature": None,
                "docstring": _extract_docstring(body_node),
            })
            # Recurse into the class body — new scope is class qualname, not in func
            if body_node:
                for child in body_node.children:
                    _visit(child, qualname, False)
            return  # don't fall through to generic child walk

        # ── function_definition / async_function_definition ────────────────
        if ntype in ("function_definition", "async_function_definition"):
            name_node = node.child_by_field_name("name")
            if name_node is None:
                return
            func_name = name_node.text.decode("utf-8", errors="replace") if name_node.text else ""

            if scope_prefix and not in_func:
                node_type = "method"
                qualname = f"{scope_prefix}.{func_name}"
            elif scope_prefix and in_func:
                node_type = "function"
                qualname = f"{scope_prefix}.<locals>.{func_name}"
            else:
                node_type = "function"
                qualname = func_name

            base_qname = f"{rel_path}::{qualname}"
            qname = _get_unique_qname(base_qname)
            body_node = node.child_by_field_name("body")
            entities.append({
                "node_type": node_type,
                "name": func_name,
                "qualified_name": qname,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "signature": _build_signature(node, src_bytes),
                "docstring": _extract_docstring(body_node),
            })
            # Recurse into the body — new scope is function qualname, in func
            if body_node:
                for child in body_node.children:
                    _visit(child, qualname, True)
            return

        # ── import_statement ───────────────────────────────────────────────
        if ntype == "import_statement":
            # e.g. ``import os, sys`` or ``import os as my_os``
            for child in node.children:
                module_path = ""
                if child.type == "dotted_name":
                    module_path = child.text.decode("utf-8", errors="replace") if child.text else ""
                elif child.type == "aliased_import":
                    name_child = child.child_by_field_name("name")
                    if name_child and name_child.text:
                        module_path = name_child.text.decode("utf-8", errors="replace")
                if module_path:
                    qname = f"{rel_path}::import:{module_path}"
                    # Avoid duplicates from re-importing the same module
                    if not any(e["qualified_name"] == qname for e in entities):
                        entities.append({
                            "node_type": "import",
                            "name": module_path,
                            "qualified_name": qname,
                            "start_line": node.start_point[0] + 1,
                            "end_line": node.end_point[0] + 1,
                            "signature": None,
                            "docstring": None,
                        })
            return

        if ntype == "import_from_statement":
            # e.g. ``from os.path import join, exists``
            module_node = node.child_by_field_name("module_name")
            module_path = ""
            if module_node and module_node.text:
                module_path = module_node.text.decode("utf-8", errors="replace")
            if module_path:
                qname = f"{rel_path}::import:{module_path}"
                # Avoid duplicates from the same file importing the same module twice
                if not any(e["qualified_name"] == qname for e in entities):
                    entities.append({
                        "node_type": "import",
                        "name": module_path,
                        "qualified_name": qname,
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                        "signature": None,
                        "docstring": None,
                    })
            return

        # ── generic: walk children (module-level / decorated / etc.) ───────
        for child in node.children:
            _visit(child, scope_prefix, in_func)

    _visit(tree.root_node, "", False)
    return entities


async def _parse_python_files(
    workspace: str,
    repo_id: str,
    job_id: str,
    log,
) -> dict:
    """Walk all .py files in *workspace*, parse with tree-sitter, and bulk-insert
    ``File`` + ``GraphNode`` rows into the database.

    Returns a stats dict: {"files_parsed", "files_failed", "nodes_inserted"}.
    """
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser

    from app.database import get_db_context
    from app.models import File, GraphNode

    PY_LANGUAGE = Language(tspython.language())
    parser = Parser(PY_LANGUAGE)

    repo_uuid = uuid.UUID(repo_id)
    workspace_path = Path(workspace)

    # Collect all .py files upfront so we can interpolate progress
    py_files = [
        f for f in workspace_path.rglob("*.py")
        if f.is_file() and not any(part in _PARSE_SKIP_DIRS for part in f.parts)
    ]
    total_files = len(py_files)
    log.info("Python files discovered", count=total_files)

    files_parsed = 0
    files_failed = 0
    nodes_inserted = 0

    # Progress window: detect_language ended at 15 %, parsing ends at 30 %
    PROGRESS_START = STAGE_PROGRESS["detecting_language"]  # 15
    PROGRESS_END = STAGE_PROGRESS["parsing"]               # 30

    async with get_db_context() as db:
        pending_files: list[File] = []
        pending_nodes: list[GraphNode] = []

        for idx, py_file in enumerate(py_files):
            rel_path = py_file.relative_to(workspace_path).as_posix()

            try:
                src_bytes = py_file.read_bytes()
            except Exception as exc:
                log.warning("Cannot read file — skipping", path=rel_path, error=str(exc))
                files_failed += 1
                continue

            # Compute git-compatible SHA before parsing (fast, independent)
            try:
                sha = _compute_sha(py_file)
            except Exception:
                sha = None

            # Count non-empty lines (same metric as _count_loc)
            try:
                loc = sum(1 for line in src_bytes.decode("utf-8", errors="ignore").splitlines() if line.strip())
            except Exception:
                loc = None

            # Parse with tree-sitter — never let a bad file abort the loop
            try:
                tree = parser.parse(src_bytes)
                entities = _walk_python_ast(tree, src_bytes, rel_path)
            except Exception as exc:
                log.warning("Tree-sitter parse failed — skipping", path=rel_path, error=str(exc))
                files_failed += 1
                continue

            # Build File ORM object
            file_obj = File(
                id=uuid.uuid4(),
                repository_id=repo_uuid,
                path=rel_path,
                language="python",
                loc=loc,
                sha=sha,
            )
            pending_files.append(file_obj)

            # Build GraphNode ORM objects
            for entity in entities:
                node_obj = GraphNode(
                    id=uuid.uuid4(),
                    repository_id=repo_uuid,
                    file_id=file_obj.id,
                    node_type=entity["node_type"],
                    name=entity["name"],
                    qualified_name=entity["qualified_name"],
                    start_line=entity["start_line"],
                    end_line=entity["end_line"],
                    signature=entity["signature"],
                    docstring=entity["docstring"],
                )
                pending_nodes.append(node_obj)

            files_parsed += 1

            # ── Periodic batch flush ───────────────────────────────────────
            if len(pending_files) >= _PARSE_BATCH_SIZE:
                db.add_all(pending_files)
                db.add_all(pending_nodes)
                await db.flush()
                nodes_inserted += len(pending_nodes)
                pending_files.clear()
                pending_nodes.clear()

                # Interpolate progress between PROGRESS_START and PROGRESS_END
                pct = PROGRESS_START + int(
                    (idx + 1) / max(total_files, 1) * (PROGRESS_END - PROGRESS_START)
                )
                await _update_job(job_id, "parsing", pct)
                log.debug("Batch flushed", files_so_far=files_parsed, progress_pct=pct)

        # ── Final flush for the last (possibly partial) batch ──────────────
        if pending_files:
            db.add_all(pending_files)
            db.add_all(pending_nodes)
            await db.flush()
            nodes_inserted += len(pending_nodes)

        # Commit everything in one shot
        await db.commit()

    # Bump progress to the full 30 % milestone
    await _update_job(job_id, "parsing", PROGRESS_END)

    return {
        "files_parsed": files_parsed,
        "files_failed": files_failed,
        "nodes_inserted": nodes_inserted,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Task: Parse (Sprint 3)
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=1)
def parse_task(self, prev_result: dict) -> dict:
    """
    Stage 3: Walk all .py files, parse with tree-sitter, and bulk-insert
    ``File`` + ``GraphNode`` rows into the database.

    Skips venv / node_modules / .git / __pycache__ / migrations.
    Individual file failures are logged and skipped — they never abort the task.
    On hard failure the task retries once (max_retries=1) then marks the job failed.
    """
    repo_id = prev_result["repo_id"]
    job_id = prev_result["job_id"]
    workspace = prev_result["workspace"]

    log = logger.bind(task="parse", repo_id=repo_id)
    log.info("Starting parse stage")

    try:
        _run_async(_update_job(job_id, "parsing", STAGE_PROGRESS["parsing"]))
        stats = _run_async(_parse_python_files(workspace, repo_id, job_id, log))
        log.info("Parse stage complete", **stats)
        return {**prev_result, "parse_stats": stats}

    except Exception as exc:
        log.error("Parse stage failed", error=str(exc))
        _run_async(_update_job(job_id, "failed", 0, str(exc)))
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4: Graph Building Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_import_to_file(
    module_str: str,
    current_file_path: str,
    repo_files: dict[str, uuid.UUID],
) -> tuple[bool, str, uuid.UUID | None]:
    """Resolve an imported module string to an internal repo file or external package."""
    if module_str.startswith("."):
        dots = len(module_str) - len(module_str.lstrip("."))
        subpath = module_str.lstrip(".")
        current_parts = Path(current_file_path).parent.parts
        if dots > len(current_parts) + 1:
            return False, module_str, None
        base_parts = current_parts[: len(current_parts) - (dots - 1)] if (dots - 1) > 0 else current_parts
        target_base = "/".join(base_parts)
        candidate = f"{target_base}/{subpath.replace('.', '/')}".strip("/") if subpath else "/".join(base_parts)
    else:
        candidate = module_str.replace(".", "/")

    if f"{candidate}.py" in repo_files:
        p = f"{candidate}.py"
        return True, p, repo_files[p]
    if f"{candidate}/__init__.py" in repo_files:
        p = f"{candidate}/__init__.py"
        return True, p, repo_files[p]

    for repo_p, fid in repo_files.items():
        if repo_p.endswith(f"/{candidate}.py") or repo_p == f"{candidate}.py":
            return True, repo_p, fid
        if repo_p.endswith(f"/{candidate}/__init__.py") or repo_p == f"{candidate}/__init__.py":
            return True, repo_p, fid

    top_pkg = module_str.lstrip(".").split(".")[0] or module_str
    return False, top_pkg, None


def _extract_ast_calls_and_bases(src_bytes: bytes) -> tuple[dict[str, tuple[str, str]], dict[str, list[str]], list[dict]]:
    """Extract symbol-level imports, class bases, and call expressions from source."""
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser

    PY_LANGUAGE = Language(tspython.language())
    parser = Parser(PY_LANGUAGE)
    tree = parser.parse(src_bytes)
    root = tree.root_node

    # 1. Imports mapping: local_name -> (module_str, original_symbol)
    file_imports: dict[str, tuple[str, str]] = {}
    ambiguous_imports: set[str] = set()
    for node in root.children:
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    m_text = child.text.decode("utf-8", errors="replace")
                    file_imports[m_text] = (m_text, m_text)
                elif child.type == "aliased_import":
                    name_child = child.child_by_field_name("name")
                    alias_child = child.child_by_field_name("alias")
                    if name_child and alias_child:
                        file_imports[alias_child.text.decode()] = (name_child.text.decode(), name_child.text.decode())
        elif node.type == "import_from_statement":
            mod_node = node.child_by_field_name("module_name")
            mod_str = mod_node.text.decode("utf-8", errors="replace") if mod_node else ""
            past_import = False
            for child in node.children:
                if child.type == "import":
                    past_import = True
                    continue
                if not past_import:
                    continue
                if child.type == "dotted_name":
                    sym = child.text.decode("utf-8", errors="replace")
                    if sym in file_imports and file_imports[sym][0] != mod_str:
                        ambiguous_imports.add(sym)
                    file_imports[sym] = (mod_str, sym)
                elif child.type == "aliased_import":
                    name_child = child.child_by_field_name("name")
                    alias_child = child.child_by_field_name("alias")
                    if name_child and alias_child:
                        orig_name = name_child.text.decode()
                        alias_name = alias_child.text.decode()
                        if alias_name in file_imports and file_imports[alias_name][0] != mod_str:
                            ambiguous_imports.add(alias_name)
                        file_imports[alias_name] = (mod_str, orig_name)

    for amb in ambiguous_imports:
        file_imports.pop(amb, None)

    # 2. Base classes & Calls
    class_bases: dict[str, list[str]] = {}
    calls: list[dict] = []

    def _walk(node, current_class, current_func, func_scope, var_types):
        ntype = node.type
        if ntype == "assignment":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left and right and right.type == "call":
                fn = right.child_by_field_name("function")
                if fn and fn.type == "identifier":
                    var_name = left.text.decode("utf-8", errors="replace")
                    cls_name = fn.text.decode("utf-8", errors="replace")
                    var_types[var_name] = cls_name

        if ntype == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                c_name = name_node.text.decode("utf-8", errors="replace")
                superclasses_node = node.child_by_field_name("superclasses")
                bases = []
                if superclasses_node:
                    for arg in superclasses_node.children:
                        if arg.type in ("identifier", "attribute"):
                            bases.append(arg.text.decode("utf-8", errors="replace"))
                class_bases[c_name] = bases

                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        _walk(child, c_name, current_func, func_scope, var_types.copy())
                return

        if ntype in ("function_definition", "async_function_definition"):
            name_node = node.child_by_field_name("name")
            if name_node:
                f_name = name_node.text.decode("utf-8", errors="replace")
                scope = f"{current_class}.{f_name}" if current_class else f_name
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        _walk(child, current_class, f_name, scope, var_types.copy())
                return

        if ntype == "call":
            fn_node = node.child_by_field_name("function")
            if fn_node and current_func:
                if fn_node.type == "identifier":
                    calls.append({
                        "caller_name": current_func,
                        "caller_scope": func_scope,
                        "current_class": current_class,
                        "callee_text": fn_node.text.decode("utf-8", errors="replace"),
                        "callee_type": "direct",
                        "receiver": None,
                        "method_name": None,
                        "line": node.start_point[0] + 1,
                    })
                elif fn_node.type == "attribute":
                    obj_node = fn_node.child_by_field_name("object")
                    attr_node = fn_node.child_by_field_name("attribute")
                    if obj_node and attr_node:
                        receiver = obj_node.text.decode("utf-8", errors="replace")
                        method = attr_node.text.decode("utf-8", errors="replace")
                        inferred_cls = var_types.get(receiver)
                        calls.append({
                            "caller_name": current_func,
                            "caller_scope": func_scope,
                            "current_class": current_class,
                            "callee_text": fn_node.text.decode("utf-8", errors="replace"),
                            "callee_type": "method",
                            "receiver": receiver,
                            "inferred_class": inferred_cls,
                            "method_name": method,
                            "line": node.start_point[0] + 1,
                        })

        for child in node.children:
            _walk(child, current_class, current_func, func_scope, var_types)

    _walk(root, None, None, None, {})
    return file_imports, class_bases, calls


async def _build_repo_graph(
    workspace: str,
    repo_id: str,
    job_id: str,
    log,
) -> dict:
    """Build graph_edges from graph_nodes, files, and workspace ASTs."""
    from sqlalchemy import select
    from app.database import get_db_context
    from app.models import File, GraphNode, GraphEdge

    repo_uuid = uuid.UUID(repo_id)
    workspace_path = Path(workspace)

    PROGRESS_START = STAGE_PROGRESS["parsing"]         # 30
    PROGRESS_END = STAGE_PROGRESS["building_graph"]     # 50

    async with get_db_context() as db:
        # 1. Fetch all existing Files and GraphNodes for this repository
        files_res = await db.execute(select(File).where(File.repository_id == repo_uuid))
        files = files_res.scalars().all()
        repo_files: dict[str, uuid.UUID] = {f.path: f.id for f in files}
        total_files = len(files)

        nodes_res = await db.execute(select(GraphNode).where(GraphNode.repository_id == repo_uuid))
        existing_nodes = nodes_res.scalars().all()

        nodes_by_id = {n.id: n for n in existing_nodes}
        nodes_by_qname = {n.qualified_name: n for n in existing_nodes}
        nodes_by_file_and_name: dict[tuple[uuid.UUID, str], list[GraphNode]] = defaultdict(list)
        for n in existing_nodes:
            if n.file_id:
                nodes_by_file_and_name[(n.file_id, n.name)].append(n)

        # 2. Phase 1: Ensure Module Nodes exist for all internal files
        new_nodes: list[GraphNode] = []
        file_module_node: dict[uuid.UUID, uuid.UUID] = {}

        for f in files:
            mod_qname = f"{f.path}::module"
            if mod_qname in nodes_by_qname:
                file_module_node[f.id] = nodes_by_qname[mod_qname].id
            else:
                mod_node = GraphNode(
                    id=uuid.uuid4(),
                    repository_id=repo_uuid,
                    file_id=f.id,
                    node_type="module",
                    name=Path(f.path).stem,
                    qualified_name=mod_qname,
                    start_line=1,
                    end_line=1,
                )
                new_nodes.append(mod_node)
                nodes_by_qname[mod_qname] = mod_node
                file_module_node[f.id] = mod_node.id

        # 3. Cache or create Synthetic External Nodes
        external_nodes: dict[str, uuid.UUID] = {}
        for n in existing_nodes:
            if n.node_type == "external":
                external_nodes[n.name] = n.id

        def get_or_create_external_node(pkg: str) -> uuid.UUID:
            if pkg in external_nodes:
                return external_nodes[pkg]
            qname = f"external::{pkg}"
            if qname in nodes_by_qname:
                ext_id = nodes_by_qname[qname].id
                external_nodes[pkg] = ext_id
                return ext_id
            ext_node = GraphNode(
                id=uuid.uuid4(),
                repository_id=repo_uuid,
                file_id=None,
                node_type="external",
                name=pkg,
                qualified_name=qname,
            )
            new_nodes.append(ext_node)
            external_nodes[pkg] = ext_node.id
            nodes_by_qname[qname] = ext_node
            return ext_node.id

        # Flush any new module or external nodes before generating foreign keys
        if new_nodes:
            db.add_all(new_nodes)
            await db.flush()

        # 4. Resolve Edges
        pending_edges: list[GraphEdge] = []
        edges_resolved = 0
        edges_external = 0
        edges_skipped_ambiguous = 0

        # Helper to resolve symbol via file_imports
        def resolve_symbol(sym_name: str, file_imports: dict[str, tuple[str, str]], current_rel: str) -> tuple[uuid.UUID | None, float]:
            if sym_name not in file_imports:
                return None, 0.0
            mod_str, orig_name = file_imports[sym_name]
            is_int, target_path, target_fid = _resolve_import_to_file(mod_str, current_rel, repo_files)
            if is_int and target_fid:
                candidates = nodes_by_file_and_name.get((target_fid, orig_name), [])
                if candidates:
                    return candidates[0].id, 0.8
                return file_module_node.get(target_fid), 0.7
            elif not is_int:
                return get_or_create_external_node(target_path), 0.0
            return None, 0.0

        # 4a. Resolve `imports` edges from graph_nodes
        import_nodes = [n for n in existing_nodes if n.node_type == "import"]
        for imp in import_nodes:
            src_file_path = imp.qualified_name.split("::")[0]
            is_internal, target_id, target_fid = _resolve_import_to_file(imp.name, src_file_path, repo_files)
            
            if is_internal and target_fid:
                target_nid = file_module_node.get(target_fid)
                if target_nid:
                    pending_edges.append(GraphEdge(
                        repository_id=repo_uuid,
                        source_node_id=imp.id,
                        target_node_id=target_nid,
                        edge_type="imports",
                        confidence=1.0,
                    ))
                    edges_resolved += 1
            else:
                ext_nid = get_or_create_external_node(target_id)
                pending_edges.append(GraphEdge(
                    repository_id=repo_uuid,
                    source_node_id=imp.id,
                    target_node_id=ext_nid,
                    edge_type="imports",
                    confidence=0.0,
                ))
                edges_external += 1

        # Cache for parsed __init__.py symbol imports
        init_imports_cache: dict[str, dict[str, tuple[str, str]]] = {}

        def get_init_imports(init_path: str) -> dict[str, tuple[str, str]]:
            if init_path not in init_imports_cache:
                init_file = workspace_path / init_path
                if init_file.is_file():
                    try:
                        src_b = init_file.read_bytes()
                        imps, _, _ = _extract_ast_calls_and_bases(src_b)
                        init_imports_cache[init_path] = imps
                    except Exception:
                        init_imports_cache[init_path] = {}
                else:
                    init_imports_cache[init_path] = {}
            return init_imports_cache[init_path]

        # 4b. Resolve `extends` & `calls` across workspace files
        for idx, f in enumerate(files):
            py_path = workspace_path / f.path
            if not py_path.is_file():
                continue
            try:
                src_bytes = py_path.read_bytes()
                file_imports, class_bases, file_calls = _extract_ast_calls_and_bases(src_bytes)
            except Exception:
                continue

            if f.path.endswith("__init__.py"):
                init_imports_cache[f.path] = file_imports

            # Extends resolution
            for c_name, bases in class_bases.items():
                c_nodes = nodes_by_file_and_name.get((f.id, c_name), [])
                c_node = next((n for n in c_nodes if n.node_type == "class"), None)
                if not c_node:
                    continue
                for b_name in bases:
                    raw_base = b_name.split(".")[-1]
                    same_file_base = next((n for n in nodes_by_file_and_name.get((f.id, raw_base), []) if n.node_type == "class"), None)
                    if same_file_base:
                        pending_edges.append(GraphEdge(
                            repository_id=repo_uuid,
                            source_node_id=c_node.id,
                            target_node_id=same_file_base.id,
                            edge_type="extends",
                            confidence=1.0,
                        ))
                        edges_resolved += 1
                    else:
                        tgt_id, conf = resolve_symbol(raw_base, file_imports, f.path)
                        if tgt_id:
                            if conf > 0.0:
                                edges_resolved += 1
                            else:
                                edges_external += 1
                            pending_edges.append(GraphEdge(
                                repository_id=repo_uuid,
                                source_node_id=c_node.id,
                                target_node_id=tgt_id,
                                edge_type="extends",
                                confidence=conf,
                            ))
                        else:
                            ext_id = get_or_create_external_node(raw_base)
                            pending_edges.append(GraphEdge(
                                repository_id=repo_uuid,
                                source_node_id=c_node.id,
                                target_node_id=ext_id,
                                edge_type="extends",
                                confidence=0.0,
                            ))
                            edges_external += 1

            # Calls resolution (Tier a-f)
            for call in file_calls:
                caller_nodes = nodes_by_file_and_name.get((f.id, call["caller_name"]), [])
                caller_node = next((n for n in caller_nodes if n.node_type in ("function", "method")), None)
                if not caller_node:
                    continue

                target_id = None
                confidence = 0.0

                # Tier a: direct sibling call
                if call["callee_type"] == "direct":
                    callee_candidates = nodes_by_file_and_name.get((f.id, call["callee_text"]), [])
                    callee_node = next((n for n in callee_candidates if n.node_type in ("function", "class")), None)
                    if callee_node:
                        target_id = callee_node.id
                        confidence = 1.0
                    else:
                        # Tier c: imported function or class
                        target_id, confidence = resolve_symbol(call["callee_text"], file_imports, f.path)

                # Tier b: self.method() / cls.method()
                elif call["callee_type"] == "method" and call["receiver"] in ("self", "cls") and call["current_class"]:
                    m_name = call["method_name"]
                    c_name = call["current_class"]
                    qname = f"{f.path}::{c_name}.{m_name}"
                    if qname in nodes_by_qname:
                        target_id = nodes_by_qname[qname].id
                        confidence = 0.9
                    else:
                        # 1-level inheritance walk
                        bases = class_bases.get(c_name, [])
                        for b in bases:
                            raw_b = b.split(".")[-1]
                            b_qname = f"{f.path}::{raw_b}.{m_name}"
                            if b_qname in nodes_by_qname:
                                target_id = nodes_by_qname[b_qname].id
                                confidence = 0.7
                                break

                # Tier d: local variable constructor inference: x = MyClass(); x.method()
                elif call["callee_type"] == "method" and call.get("inferred_class"):
                    inf_cls = call["inferred_class"]
                    m_name = call["method_name"]
                    inf_qname = f"{f.path}::{inf_cls}.{m_name}"
                    if inf_qname in nodes_by_qname:
                        target_id = nodes_by_qname[inf_qname].id
                        confidence = 0.6

                # Tier e: module-qualified call: imported_mod.func() or ImportedClass.method()
                elif call["callee_type"] == "method" and call.get("receiver") in file_imports:
                    recv = call["receiver"]
                    m_name = call.get("method_name")
                    if m_name:
                        mod_str, orig_sym = file_imports[recv]
                        is_int, target_path, target_fid = _resolve_import_to_file(mod_str, f.path, repo_files)

                        target_fids = [target_fid] if (is_int and target_fid) else []
                        if mod_str and mod_str != orig_sym:
                            sub_mod = f"{mod_str}.{orig_sym}"
                            is_sub, _, sub_fid = _resolve_import_to_file(sub_mod, f.path, repo_files)
                            if is_sub and sub_fid and sub_fid not in target_fids:
                                target_fids.append(sub_fid)

                        for tfid in target_fids:
                            candidates = nodes_by_file_and_name.get((tfid, m_name), [])
                            target_node = next((n for n in candidates if n.node_type in ("function", "class")), None)
                            if not target_node:
                                target_node = next((n for n in candidates if n.node_type == "method"), None)
                            if target_node:
                                target_id = target_node.id
                                confidence = 0.8
                                break

                        # Tier f: __init__.py submodule re-export
                        if not target_id and is_int and target_path and target_path.endswith("__init__.py"):
                            init_imports = get_init_imports(target_path)
                            if m_name in init_imports:
                                submod_str, orig_sub_sym = init_imports[m_name]
                                is_sub_int, sub_target_path, sub_target_fid = _resolve_import_to_file(
                                    submod_str, target_path, repo_files
                                )
                                if is_sub_int and sub_target_fid:
                                    sub_cands = nodes_by_file_and_name.get((sub_target_fid, orig_sub_sym), [])
                                    sub_node = next((n for n in sub_cands if n.node_type in ("function", "class")), None)
                                    if not sub_node:
                                        sub_node = next((n for n in sub_cands if n.node_type == "method"), None)
                                    if sub_node:
                                        target_id = sub_node.id
                                        confidence = 0.75

                if target_id:
                    if confidence > 0.0:
                        edges_resolved += 1
                    else:
                        edges_external += 1
                    pending_edges.append(GraphEdge(
                        repository_id=repo_uuid,
                        source_node_id=caller_node.id,
                        target_node_id=target_id,
                        edge_type="calls",
                        confidence=confidence,
                    ))
                else:
                    edges_skipped_ambiguous += 1

            # Flush periodically and interpolate progress
            if len(pending_edges) >= _PARSE_BATCH_SIZE:
                db.add_all(pending_edges)
                await db.flush()
                pending_edges.clear()

            pct = PROGRESS_START + int((idx + 1) / max(total_files, 1) * (PROGRESS_END - PROGRESS_START))
            await _update_job(job_id, "building_graph", pct)

        if pending_edges:
            db.add_all(pending_edges)
            await db.flush()

        await db.commit()

    await _update_job(job_id, "building_graph", PROGRESS_END)

    return {
        "edges_resolved": edges_resolved,
        "edges_external": edges_external,
        "edges_skipped_ambiguous": edges_skipped_ambiguous,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Task: Build Graph (Sprint 4)
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=1)
def build_graph_task(self, prev_result: dict) -> dict:
    """
    Stage 4: Resolve relationships and write graph edges (imports, extends, calls).
    """
    repo_id = prev_result["repo_id"]
    job_id = prev_result["job_id"]
    workspace = prev_result["workspace"]

    log = logger.bind(task="build_graph", repo_id=repo_id)
    log.info("Starting build_graph stage")

    try:
        _run_async(_update_job(job_id, "building_graph", STAGE_PROGRESS["building_graph"]))
        stats = _run_async(_build_repo_graph(workspace, repo_id, job_id, log))
        log.info("Build graph stage complete", **stats)
        return {**prev_result, "graph_stats": stats}

    except Exception as exc:
        log.error("Build graph stage failed", error=str(exc))
        _run_async(_update_job(job_id, "failed", 0, str(exc)))
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# Task: Embed (Sprint 5)
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=1)
def embed_task(self, prev_result: dict) -> dict:
    """
    Stage 5: Generate embeddings for all graph nodes and doc chunks.
    Implemented in Sprint 5.
    """
    job_id = prev_result["job_id"]
    _run_async(_update_job(job_id, "embedding", STAGE_PROGRESS["embedding"]))
    return prev_result


# ─────────────────────────────────────────────────────────────────────────────
# Task: Static Analysis (Sprint 6)
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=1)
def static_analysis_task(self, prev_result: dict) -> dict:
    """
    Stage 6: Run Ruff, Bandit, ESLint and store results.
    Implemented in Sprint 6.
    """
    job_id = prev_result["job_id"]
    _run_async(_update_job(job_id, "static_analysis", STAGE_PROGRESS["static_analysis"]))
    return prev_result


# ─────────────────────────────────────────────────────────────────────────────
# Task: Report Generation (Sprint 6)
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=1)
def report_generation_task(self, prev_result: dict) -> dict:
    """
    Stage 7: Compute Health Score and write health_report record.
    Implemented in Sprint 6.
    """
    job_id = prev_result["job_id"]
    _run_async(_update_job(job_id, "report_generation", STAGE_PROGRESS["report_generation"]))
    _run_async(_update_job(job_id, "done", 100))
    return prev_result


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point: run_pipeline
# Enqueues the full Celery chain — called from the API layer.
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task
def run_pipeline(repo_id: str, job_id: str, source_url: str):
    """
    Entry point: builds and dispatches the full task chain.
    Each stage receives the result dict from the previous stage.
    """
    pipeline = chain(
        clone_task.s(repo_id, job_id, source_url),
        detect_language_task.s(),
        parse_task.s(),
        build_graph_task.s(),
        embed_task.s(),
        static_analysis_task.s(),
        report_generation_task.s(),
    )
    pipeline.apply_async()
