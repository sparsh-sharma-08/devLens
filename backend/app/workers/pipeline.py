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
import sys
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

# ── Stage 6: Static Analysis Constants & Severity Mapping ─────────────────────

# Maximum execution time per static analysis tool CLI process
STATIC_ANALYSIS_TIMEOUT_SECONDS: int = 90

# Fallback severity for any Ruff rule prefix not explicitly mapped
DEFAULT_SEVERITY: str = "info"

# 1. Exact-code overrides checked BEFORE prefix matching
RUFF_EXACT_SEVERITY_OVERRIDES: dict[str, str] = {
    # Undefined name at runtime -> NameError crash
    "F821": "high",
}

# 2. Prefix-based severity mappings (checked after exact-code overrides)
RUFF_PREFIX_SEVERITY_MAP: list[tuple[str, str]] = [
    # Critical: Fatal syntax errors & unparseable files
    ("E9", "critical"),
    ("PLE", "critical"),

    # High: Security vulnerabilities, async deadlocks, left-in debuggers
    ("S", "high"),
    ("ASYNC", "high"),
    ("T10", "high"),

    # Medium: Probable runtime logic bugs & anti-patterns
    ("F", "medium"),
    ("B", "medium"),
    ("PLW", "medium"),
    ("TRY", "medium"),
    ("BLE", "medium"),
    ("RUF", "medium"),
    ("C90", "medium"),

    # Low: Performance, code smells, complexity, deprecations
    ("PERF", "low"),
    ("SIM", "low"),
    ("PLR", "low"),
    ("PLC", "low"),
    ("C4", "low"),
    ("UP", "low"),
    ("ARG", "low"),
    ("DTZ", "low"),
    ("PTH", "low"),
    ("RET", "low"),
    ("SLF", "low"),

    # Info: Formatting, docstrings, conventions, comments
    ("E", "info"),
    ("W", "info"),
    ("I", "info"),
    ("D", "info"),
    ("N", "info"),
    ("Q", "info"),
    ("COM", "info"),
    ("T20", "info"),
    ("TD", "info"),
    ("FIX", "info"),
    ("ERA", "info"),
    ("FA", "info"),
    ("INP", "info"),
    ("TCH", "info"),
]

# Sorted by descending prefix length once at module load to guarantee longer,
# more specific prefixes match before shorter ones (e.g. SIM/SLF before S, FA/FIX before F)
_SORTED_RUFF_PREFIXES: list[tuple[str, str]] = sorted(
    RUFF_PREFIX_SEVERITY_MAP, key=lambda x: -len(x[0])
)

BANDIT_SEVERITY_MAP: dict[str, str] = {
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
}


def _map_ruff_severity(code: str | None, unmapped_counter: dict[str, int]) -> str:
    """
    Map a Ruff rule code to schema severity ('critical'|'high'|'medium'|'low'|'info').
    Checks exact-code overrides first, then prefix mapping, defaulting to DEFAULT_SEVERITY.
    Tracks unmapped rule prefixes for post-validation reporting.
    """
    if not code:
        return DEFAULT_SEVERITY

    # 1. Exact-code override checked first
    if code in RUFF_EXACT_SEVERITY_OVERRIDES:
        return RUFF_EXACT_SEVERITY_OVERRIDES[code]

    # 2. Prefix matching using descending-length sorted prefixes
    for prefix, sev in _SORTED_RUFF_PREFIXES:
        if code.startswith(prefix):
            return sev

    # 3. Explicit default fallback
    prefix_part = "".join(c for c in code if c.isalpha()) or code[:3]
    unmapped_counter[prefix_part] = unmapped_counter.get(prefix_part, 0) + 1
    return DEFAULT_SEVERITY


def _map_bandit_severity(severity_str: str | None) -> str:
    """Map Bandit's native severity (LOW/MEDIUM/HIGH) to schema severity."""
    return BANDIT_SEVERITY_MAP.get((severity_str or "").upper(), "info")


def _is_test_path(rel_path: str) -> bool:
    """Return True if relative file path represents test code or fixtures.

    Matches:
      - Any path component named 'tests', 'test', or 'testing' (directory names)
      - Files: test_*.py, *_test.py, conftest.py
      - Testing utility modules: testing.py, *_testing.py  (e.g. click/testing.py)
    """
    p = Path(rel_path)
    if any(part in ("tests", "test", "testing") for part in p.parts):
        return True
    filename = p.name.lower()
    return (
        filename.startswith("test_")
        or filename.endswith("_test.py")
        or filename == "conftest.py"
        or filename == "testing.py"
        or filename.endswith("_testing.py")
    )


def _is_non_production_path(rel_path: str) -> bool:
    """Return True if relative file path represents tests, developer tooling, examples, or docs.

    Used to guard the hard health-score ceiling from false-positive ship-blocker flags on
    maintenance scripts, build utilities, doc examples, and test fixtures that are never
    shipped or executed in production runtime environments.
    """
    if _is_test_path(rel_path):
        return True
    p = Path(rel_path)
    return any(part in ("tools", "scripts", "examples", "docs", "benchmarks", "fixtures") for part in p.parts)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 7: Health Score & Report Generation Constants
# ─────────────────────────────────────────────────────────────────────────────

# Curated subset of rule codes that represent genuine, unambiguous ship-blockers
# in production code (caps overall_score and security_score to 70)
CEILING_CRITICAL_RULES: frozenset[str] = frozenset({
    "B601",  # paramiko shell enabled (direct RCE)
    "B602",  # subprocess call with shell=True and dynamic arguments
    "B604",  # function call with shell=True
    "S602",  # ruff flake8-bandit shell=True
    "B605",  # start process with a shell
    "B608",  # hardcoded SQL formatted string (SQL injection)
    "S608",  # ruff SQL injection
    "B703",  # django mark_safe with variable (XSS)
})

# Curated high-severity triggers (caps overall_score and security_score to 85)
CEILING_HIGH_RULES: frozenset[str] = frozenset({
    "B501",  # request without certificate verification
    "B502",  # SSL/TLS use of deprecated unsafe protocol version
    "B503",  # SSL wrap_socket with deprecated options
    "B504",  # SSL without version check
    "B506",  # yaml.load without safe Loader
    "S506",  # ruff unsafe yaml.load
    "B612",  # logging config listen socket
})

# Defect density penalty weights (points deducted per KLOC)
STAGE7_SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 15.0,
    "high": 6.0,
    "medium": 2.0,
    "low": 0.4,
}
STAGE7_INFO_WEIGHT: float = 0.02
STAGE7_INFO_MAX_PENALTY: float = 5.0

STAGE7_SEV_RANK: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "info": 0,
}




# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _run_async(coro):
    """Run an async coroutine from synchronous Celery task context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


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
        # Clear existing workspace if present (e.g. re-indexing or retry)
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir, ignore_errors=True)
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


def _cleanup_workspace(workspace: str | Path, log) -> int:
    """Safely delete the workspace directory and return bytes freed."""
    p = Path(workspace)
    if not p.exists():
        return 0
    size_bytes = 0
    try:
        for f in p.rglob("*"):
            if f.is_file() and not f.is_symlink():
                try:
                    size_bytes += f.stat().st_size
                except OSError:
                    pass
        shutil.rmtree(p, ignore_errors=True)
        log.info(
            "Workspace directory cleaned up",
            path=str(p),
            freed_bytes=size_bytes,
            freed_mb=round(size_bytes / (1024 * 1024), 2),
        )
    except Exception as exc:
        log.warning("Failed to clean up workspace directory", path=str(p), error=str(exc))
    return size_bytes


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
    Stage 5: Generate vector embeddings for all graph nodes in the repository.

    For each non-external, non-import graph_node we construct an
    information-rich text snippet (name + qualified_name + signature +
    docstring) and encode it with sentence-transformers/all-MiniLM-L6-v2.
    Results are stored in the `embeddings` table (Vector(384)).

    The model is loaded ONCE per Celery worker process via the module-level
    singleton in app.embeddings — subsequent repos in the same worker
    reuse the already-loaded model without re-loading from disk.
    """
    job_id = prev_result["job_id"]
    repo_id = prev_result["repo_id"]

    log = logger.bind(job_id=job_id, repo_id=repo_id, stage="embedding")
    log.info("Starting embed stage")

    try:
        _run_async(_update_job(job_id, "embedding", STAGE_PROGRESS["embedding"]))
        stats = _run_async(_embed_repo(repo_id, log))
        log.info("Embed stage complete", **stats)
        return {**prev_result, "embed_stats": stats}

    except Exception as exc:
        log.error("Embed stage failed", error=str(exc))
        _run_async(_update_job(job_id, "failed", 0, str(exc)))
        raise self.retry(exc=exc)


async def _embed_repo(repo_id: str, log) -> dict:
    """
    Embed all qualifying graph nodes for a repository and persist to DB.

    Strategy:
    - Load nodes: all node_types EXCEPT 'external' and 'import'
      (those carry no meaningful code body to embed).
    - Build text: name + qualified_name + signature + docstring.
    - Batch encode with all-MiniLM-L6-v2 (batch_size=64).
    - Delete existing embeddings for this repo (idempotent re-indexing),
      then bulk-insert new rows.

    Returns a stats dict for logging.
    """
    from sqlalchemy import select, delete
    from app.database import get_db_context
    from app.models import GraphNode, Embedding
    from app.embeddings import embed_texts, build_node_embedding_text

    repo_uuid = uuid.UUID(repo_id)

    async with get_db_context() as db:
        # ── 1. Fetch nodes eligible for embedding ─────────────────────────
        result = await db.execute(
            select(GraphNode)
            .where(
                GraphNode.repository_id == repo_uuid,
                GraphNode.node_type.notin_(["external", "import"]),
            )
        )
        nodes: list[GraphNode] = result.scalars().all()

        if not nodes:
            log.warning("No embeddable nodes found", repo_id=repo_id)
            return {"nodes_embedded": 0, "nodes_skipped": 0}

        # ── 2. Build text representations ─────────────────────────────────
        texts: list[str] = []
        valid_nodes: list[GraphNode] = []
        skipped = 0
        for node in nodes:
            text = build_node_embedding_text(node).strip()
            if not text:
                skipped += 1
                continue
            texts.append(text)
            valid_nodes.append(node)

        log.info("Built embedding texts", total=len(texts), skipped=skipped)

        # ── 3. Batch encode ────────────────────────────────────────────────
        # embed_texts() calls the module-level singleton — model is loaded
        # once per worker process, not per task invocation.
        vectors: list[list[float]] = embed_texts(texts, batch_size=64)

        # ── 4. Wipe existing CODE embeddings for this repo (idempotent) ───
        #    Scoped to source_type="code" so any future non-code embedding
        #    types (doc chunks, commit summaries, etc.) are not wiped on reindex.
        await db.execute(
            delete(Embedding).where(
                Embedding.repository_id == repo_uuid,
                Embedding.source_type == "code",
            )
        )

        # ── 5. Bulk-insert new embedding rows ─────────────────────────────
        batch_size = 256
        inserted = 0
        for i in range(0, len(valid_nodes), batch_size):
            chunk_nodes = valid_nodes[i : i + batch_size]
            chunk_vecs = vectors[i : i + batch_size]
            chunk_texts = texts[i : i + batch_size]
            for node, vector, text in zip(chunk_nodes, chunk_vecs, chunk_texts):
                emb = Embedding(
                    repository_id=repo_uuid,
                    node_id=node.id,
                    source_type="code",
                    content_excerpt=text[:1000],
                    vector=vector,
                )
                db.add(emb)
            inserted += len(chunk_nodes)
            # Flush each batch to avoid one huge ORM flush at commit
            await db.flush()

        await db.commit()

        return {
            "nodes_embedded": inserted,
            "nodes_skipped": skipped,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Task: Static Analysis (Stage 6)
# ─────────────────────────────────────────────────────────────────────────────

async def _run_tool_subprocess(
    cmd: list[str],
    cwd: Path,
    tool_name: str,
    log: structlog.BoundLogger,
) -> tuple[str, list[dict]]:
    """
    Run a static analysis CLI subprocess via asyncio.create_subprocess_exec.
    Returns (status, parsed_results) where status is 'ok' | 'timeout' | 'error'.
    Non-zero exit codes are NOT treated as crashes if parseable JSON is returned.
    """
    log.info(f"Running {tool_name} subprocess", command=cmd, cwd=str(cwd))
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=STATIC_ANALYSIS_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        log.warning(f"{tool_name} subprocess timed out", timeout_seconds=STATIC_ANALYSIS_TIMEOUT_SECONDS)
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return "timeout", []
    except Exception as exc:
        log.error(f"{tool_name} subprocess execution failed", error=str(exc))
        return "error", []

    stdout_str = stdout.decode("utf-8", errors="replace").strip()
    if not stdout_str:
        if proc.returncode == 0:
            return "ok", []
        log.warning(f"{tool_name} produced empty stdout with non-zero exit", returncode=proc.returncode, stderr=stderr.decode("utf-8", errors="replace")[:500])
        return "error", []

    import json
    try:
        # For Bandit, strip any leading non-JSON output (e.g. progress or headers)
        if tool_name == "bandit":
            json_start = stdout_str.find("{")
            if json_start != -1:
                payload = json.loads(stdout_str[json_start:])
                return "ok", payload.get("results", [])
            return "error", []
        else:
            payload = json.loads(stdout_str)
            if isinstance(payload, list):
                return "ok", payload
            return "error", []
    except Exception as exc:
        log.warning(f"Failed to parse {tool_name} JSON output", error=str(exc), stdout_sample=stdout_str[:300])
        return "error", []


async def _run_static_analysis(repo_id: str, job_id: str) -> dict:
    """
    Execute Ruff and Bandit concurrently against the repository workspace, normalize findings,
    map paths to files.id (with skip-rather-than-guess on ambiguity), scope-delete
    prior findings, and batch insert into static_analysis_results.
    """
    from app.config import get_settings
    from app.database import get_db_context
    from app.models import File, StaticAnalysisResult
    from sqlalchemy import select, delete

    settings = get_settings()
    workspace_dir = Path(settings.clone_workspace_dir) / repo_id
    log = logger.bind(stage="static_analysis", repo_id=repo_id, job_id=job_id)

    repo_uuid = uuid.UUID(repo_id)

    async with get_db_context() as db:
        # Pre-fetch known files for this repo: {rel_path: file_id}
        file_rows = await db.execute(
            select(File.id, File.path).where(File.repository_id == repo_uuid)
        )
        file_map: dict[str, uuid.UUID] = {row.path: row.id for row in file_rows}

        # Resolve CLI commands (support system binary or active venv python -m)
        ruff_bin = shutil.which("ruff") or [sys.executable, "-m", "ruff"]
        bandit_bin = shutil.which("bandit") or [sys.executable, "-m", "bandit"]

        ruff_cmd = (
            [ruff_bin, "check", "--isolated", "--output-format=json", str(workspace_dir)]
            if isinstance(ruff_bin, str)
            else ruff_bin + ["check", "--isolated", "--output-format=json", str(workspace_dir)]
        )
        bandit_cmd = (
            [bandit_bin, "-r", "-q", "-f", "json", str(workspace_dir)]
            if isinstance(bandit_bin, str)
            else bandit_bin + ["-r", "-q", "-f", "json", str(workspace_dir)]
        )

        # 1. Subprocess execution with error & timeout isolation (concurrent run via asyncio.gather)
        (ruff_status, ruff_raw), (bandit_status, bandit_raw) = await asyncio.gather(
            _run_tool_subprocess(ruff_cmd, workspace_dir, "ruff", log),
            _run_tool_subprocess(bandit_cmd, workspace_dir, "bandit", log),
        )

        pending_records: list[StaticAnalysisResult] = []
        unmapped_ruff_prefixes: dict[str, int] = {}
        analyzed_files: set[str] = set()

        # 2. Process Ruff findings
        for item in ruff_raw:
            raw_file = item.get("filename") or ""
            p = Path(raw_file)
            rel_path = (
                p.relative_to(workspace_dir).as_posix()
                if p.is_absolute() and p.is_relative_to(workspace_dir)
                else p.as_posix()
            )
            analyzed_files.add(rel_path)
            matched_file_id = file_map.get(rel_path)  # None if outside tracked .py files

            code = item.get("code")
            sev = _map_ruff_severity(code, unmapped_ruff_prefixes)
            line = item.get("location", {}).get("row") if item.get("location") else None

            pending_records.append(
                StaticAnalysisResult(
                    id=uuid.uuid4(),
                    repository_id=repo_uuid,
                    tool="ruff",
                    file_id=matched_file_id,
                    line=line,
                    severity=sev,
                    rule_id=code,
                    message=item.get("message") or "",
                )
            )

        # Dual-detection tracking: S-rules overlap with Bandit; flagged for Stage 7 health-score weighting
        # Count true Flake8-Bandit security rules (S followed by digits, e.g. S101, S608; not SIM/SLF)
        ruff_security_rule_count = sum(
            1 for item in ruff_raw
            if (code := item.get("code") or "") and code.startswith("S") and len(code) > 1 and code[1].isdigit()
        )

        # 3. Process Bandit findings
        retained_bandit_count = 0
        for item in bandit_raw:
            raw_file = item.get("filename") or ""
            p = Path(raw_file)
            rel_path = (
                p.relative_to(workspace_dir).as_posix()
                if p.is_absolute() and p.is_relative_to(workspace_dir)
                else p.as_posix()
            )
            analyzed_files.add(rel_path)

            test_id = item.get("test_id")

            # Filter out B101 (assert_used) in test files specifically — standard pytest usage,
            # not a vulnerability; retain B101 in non-test code and non-B101 in test code
            if test_id == "B101" and _is_test_path(rel_path):
                continue

            matched_file_id = file_map.get(rel_path)
            sev = _map_bandit_severity(item.get("issue_severity"))
            line = item.get("line_number")

            pending_records.append(
                StaticAnalysisResult(
                    id=uuid.uuid4(),
                    repository_id=repo_uuid,
                    tool="bandit",
                    file_id=matched_file_id,
                    line=line,
                    severity=sev,
                    rule_id=test_id,
                    message=item.get("issue_text") or "",
                )
            )
            retained_bandit_count += 1

        if unmapped_ruff_prefixes:
            log.info("Ruff rule prefixes defaulted to DEFAULT_SEVERITY", unmapped=unmapped_ruff_prefixes)

        # 4. Scoped idempotent delete prior to insertion
        await db.execute(
            delete(StaticAnalysisResult).where(
                StaticAnalysisResult.repository_id == repo_uuid,
                StaticAnalysisResult.tool.in_(["ruff", "bandit"]),
            )
        )

        # 5. Batch insert in chunks of 256
        BATCH_SIZE = 256
        for i in range(0, len(pending_records), BATCH_SIZE):
            for obj in pending_records[i : i + BATCH_SIZE]:
                db.add(obj)
            await db.flush()

        await db.commit()

        return {
            "ruff_issues": len(ruff_raw),
            "bandit_issues": retained_bandit_count,
            "ruff_security_rule_count": ruff_security_rule_count,
            "files_analyzed": len(analyzed_files),
            "ruff_status": ruff_status,
            "bandit_status": bandit_status,
        }


@celery_app.task(bind=True, max_retries=1)
def static_analysis_task(self, prev_result: dict) -> dict:
    """
    Stage 6: Run Ruff and Bandit static analysis CLI tools, map findings,
    and populate static_analysis_results.
    """
    job_id = prev_result["job_id"]
    repo_id = prev_result["repo_id"]
    log = logger.bind(task="static_analysis", repo_id=repo_id, job_id=job_id)
    log.info("Starting Stage 6: static analysis")

    _run_async(_update_job(job_id, "static_analysis", STAGE_PROGRESS["static_analysis"]))

    try:
        stats = _run_async(_run_static_analysis(repo_id, job_id))
        log.info("Static analysis completed successfully", **stats)
        prev_result.update(stats)
        return prev_result
    except Exception as exc:
        log.error("Static analysis failed", error=str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)
        raise


async def _generate_health_report(repo_id: str, job_id: str, prev_result: dict, log) -> dict:
    """
    Compute comprehensive repository health scores and write HealthReport row.
    - Normalizes defect density by KLOC
    - Proximity-based deduplication of Ruff S-rules and Bandit findings (<= 2 lines)
    - Code quality scoring (non-security bugs, smells, cosmetic penalty capped at 5 pts)
    - AST complexity scoring (long functions, large classes)
    - Graph dependency health scoring (ambiguous call edges, external node load)
    - Absolute severity ceiling (caps to 70 for critical, 85 for high in production code)
    - Scoped idempotent replacement in health_reports table
    """
    from app.database import get_db_context
    from app.models import File, GraphNode, HealthReport, StaticAnalysisResult
    from sqlalchemy import delete, func, select

    repo_uuid = uuid.UUID(repo_id)

    async with get_db_context() as db:
        # 1. Size normalization (KLOC)
        total_loc = prev_result.get("total_loc")
        if not total_loc:
            loc_res = await db.execute(
                select(func.coalesce(func.sum(File.loc), 0)).where(
                    File.repository_id == repo_uuid
                )
            )
            total_loc = loc_res.scalar() or 1000
        kloc = max(float(total_loc) / 1000.0, 1.0)

        # 2. Fetch all static analysis results with file path
        findings_stmt = (
            select(
                StaticAnalysisResult.tool,
                StaticAnalysisResult.severity,
                StaticAnalysisResult.rule_id,
                StaticAnalysisResult.line,
                File.path,
            )
            .outerjoin(File, StaticAnalysisResult.file_id == File.id)
            .where(StaticAnalysisResult.repository_id == repo_uuid)
        )
        finding_rows = (await db.execute(findings_stmt)).all()

        bandit_findings: list[dict] = []
        ruff_s_findings: list[dict] = []
        quality_findings: list[dict] = []

        for tool, sev, rule_id, line, f_path in finding_rows:
            p_str = f_path or ""
            sev_str = (sev or "info").lower()
            code_str = rule_id or ""
            line_int = line or 0

            if tool == "bandit":
                bandit_findings.append({
                    "path": p_str,
                    "severity": sev_str,
                    "rule_id": code_str,
                    "line": line_int,
                })
            elif tool == "ruff":
                # Dual detection: S followed by digits (Flake8-Bandit)
                if code_str.startswith("S") and len(code_str) > 1 and code_str[1].isdigit():
                    ruff_s_findings.append({
                        "path": p_str,
                        "severity": sev_str,
                        "rule_id": code_str,
                        "line": line_int,
                    })
                else:
                    quality_findings.append({
                        "path": p_str,
                        "severity": sev_str,
                        "rule_id": code_str,
                        "line": line_int,
                    })

        # Proximity-based dedup: index Bandit findings by path
        bandit_map: dict[str, list[dict]] = defaultdict(list)
        for bf in bandit_findings:
            bandit_map[bf["path"]].append(dict(bf))

        dual_detection_overlaps = 0
        retained_sec_findings: list[dict] = []

        for rf in ruff_s_findings:
            r_path = rf["path"]
            r_line = rf["line"]
            r_sev = rf["severity"]

            overlap_found = False
            for bf in bandit_map.get(r_path, []):
                if abs(bf["line"] - r_line) <= 2:
                    overlap_found = True
                    dual_detection_overlaps += 1
                    # Upgrade severity if Ruff severity rank is higher
                    if STAGE7_SEV_RANK.get(r_sev, 0) > STAGE7_SEV_RANK.get(bf["severity"], 0):
                        bf["severity"] = r_sev
                    break

            if not overlap_found:
                retained_sec_findings.append(rf)

        # Retain all Bandit findings (with severities potentially upgraded from overlap)
        for bf_list in bandit_map.values():
            retained_sec_findings.extend(bf_list)

        # 3. Security Score (0-100)
        sec_counts = {
            "critical": sum(1 for f in retained_sec_findings if f["severity"] == "critical"),
            "high": sum(1 for f in retained_sec_findings if f["severity"] == "high"),
            "medium": sum(1 for f in retained_sec_findings if f["severity"] == "medium"),
            "low": sum(1 for f in retained_sec_findings if f["severity"] == "low"),
        }
        sec_penalty = (
            STAGE7_SEVERITY_WEIGHTS["critical"] * sec_counts["critical"]
            + STAGE7_SEVERITY_WEIGHTS["high"] * sec_counts["high"]
            + STAGE7_SEVERITY_WEIGHTS["medium"] * sec_counts["medium"]
            + STAGE7_SEVERITY_WEIGHTS["low"] * sec_counts["low"]
        ) / kloc
        raw_security_score = max(0.0, min(100.0, 100.0 - sec_penalty))

        # 4. Code Quality / Maintainability Score (duplication_score)
        qual_counts = {
            "critical": sum(1 for f in quality_findings if f["severity"] == "critical"),
            "high": sum(1 for f in quality_findings if f["severity"] == "high"),
            "medium": sum(1 for f in quality_findings if f["severity"] == "medium"),
            "low": sum(1 for f in quality_findings if f["severity"] == "low"),
            "info": sum(1 for f in quality_findings if f["severity"] == "info"),
        }
        info_penalty = min(STAGE7_INFO_MAX_PENALTY, (qual_counts["info"] / kloc) * STAGE7_INFO_WEIGHT)
        qual_penalty = (
            (
                STAGE7_SEVERITY_WEIGHTS["critical"] * qual_counts["critical"]
                + STAGE7_SEVERITY_WEIGHTS["high"] * qual_counts["high"]
                + STAGE7_SEVERITY_WEIGHTS["medium"] * qual_counts["medium"]
                + STAGE7_SEVERITY_WEIGHTS["low"] * qual_counts["low"]
            )
            / kloc
        ) + info_penalty
        raw_quality_score = max(0.0, min(100.0, 100.0 - qual_penalty))

        # 5. Absolute Ceiling Guard
        # Check all findings in production code (exempting developer tooling, tests, examples)
        all_production_findings = [
            f for f in (retained_sec_findings + quality_findings)
            if not _is_non_production_path(f["path"])
        ]

        ceiling_triggered: str | None = None
        ceiling_rule: str | None = None
        ceiling_file: str | None = None

        for f in all_production_findings:
            if f["rule_id"] in CEILING_CRITICAL_RULES:
                ceiling_triggered = "critical"
                ceiling_rule = f["rule_id"]
                ceiling_file = f["path"]
                break

        if not ceiling_triggered:
            for f in all_production_findings:
                if f["rule_id"] in CEILING_HIGH_RULES:
                    ceiling_triggered = "high"
                    ceiling_rule = f["rule_id"]
                    ceiling_file = f["path"]
                    break

        if ceiling_triggered == "critical":
            security_score = min(raw_security_score, 70.0)
        elif ceiling_triggered == "high":
            security_score = min(raw_security_score, 85.0)
        else:
            security_score = raw_security_score

        # 6. AST Complexity Score (0-100)
        nodes_stmt = select(
            GraphNode.node_type, GraphNode.start_line, GraphNode.end_line
        ).where(
            GraphNode.repository_id == repo_uuid,
            GraphNode.node_type.in_(["function", "method", "class"]),
        )
        node_rows = (await db.execute(nodes_stmt)).all()
        total_funcs = 0
        long_funcs = 0
        total_classes = 0
        large_classes = 0

        for n_type, start_l, end_l in node_rows:
            lines = (end_l - start_l + 1) if (start_l is not None and end_l is not None) else 0
            if n_type in ("function", "method"):
                total_funcs += 1
                if lines > 50:
                    long_funcs += 1
            elif n_type == "class":
                total_classes += 1
                if lines > 300:
                    large_classes += 1

        func_ratio = (long_funcs / total_funcs) if total_funcs > 0 else 0.0
        class_ratio = (large_classes / total_classes) if total_classes > 0 else 0.0
        complexity_score = max(0.0, min(100.0, 100.0 - 20.0 * func_ratio - 15.0 * class_ratio))

        # 7. Architecture & Dependency Health Score (0-100)
        ext_res = await db.execute(
            select(func.count()).select_from(GraphNode).where(
                GraphNode.repository_id == repo_uuid,
                GraphNode.node_type == "external",
            )
        )
        ext_nodes = ext_res.scalar() or 0

        file_res = await db.execute(
            select(func.count()).select_from(File).where(File.repository_id == repo_uuid)
        )
        file_count = file_res.scalar() or 1

        graph_stats = prev_result.get("graph_stats") or {}
        edges_ambiguous = graph_stats.get("edges_skipped_ambiguous", 0)
        edges_inserted = graph_stats.get("edges_inserted", 0)

        ambiguity_ratio = (
            (edges_ambiguous / (edges_ambiguous + edges_inserted))
            if (edges_ambiguous + edges_inserted) > 0
            else 0.0
        )
        ext_ratio = (ext_nodes / (file_count * 5.0)) if file_count > 0 else 0.0
        dependency_score = max(0.0, min(100.0, 100.0 - 25.0 * ambiguity_ratio - 15.0 * ext_ratio))

        # 8. Composite Overall Health Score (0-100)
        overall_composite = (
            0.35 * security_score
            + 0.30 * raw_quality_score
            + 0.20 * complexity_score
            + 0.15 * dependency_score
        )
        if ceiling_triggered == "critical":
            overall_score = min(overall_composite, 70.0)
        elif ceiling_triggered == "high":
            overall_score = min(overall_composite, 85.0)
        else:
            overall_score = overall_composite

        metrics_json = {
            "kloc": round(kloc, 2),
            "total_loc": total_loc,
            "dedup_summary": {
                "raw_bandit": len(bandit_findings),
                "raw_ruff_s_rules": len(ruff_s_findings),
                "dual_detection_overlaps": dual_detection_overlaps,
                "retained_security_findings": len(retained_sec_findings),
            },
            "security": {
                "raw_score": round(raw_security_score, 2),
                "final_score": int(round(security_score)),
                "counts": sec_counts,
            },
            "code_quality": {
                "raw_score": round(raw_quality_score, 2),
                "final_score": int(round(raw_quality_score)),
                "info_penalty": round(info_penalty, 2),
                "counts": qual_counts,
            },
            "complexity": {
                "score": int(round(complexity_score)),
                "total_functions": total_funcs,
                "long_functions": long_funcs,
                "total_classes": total_classes,
                "large_classes": large_classes,
            },
            "dependency": {
                "score": int(round(dependency_score)),
                "total_files": file_count,
                "external_nodes": ext_nodes,
                "edges_ambiguous": edges_ambiguous,
                "edges_inserted": edges_inserted,
            },
            "ceiling": {
                "triggered": ceiling_triggered is not None,
                "level": ceiling_triggered,
                "trigger_rule": ceiling_rule,
                "trigger_file": ceiling_file,
            },
        }

        # 9. Scoped idempotent delete & persist to health_reports
        await db.execute(delete(HealthReport).where(HealthReport.repository_id == repo_uuid))

        # Note on DB column naming: The database schema defines this column as `duplication_score`
        # from an earlier design. In Stage 7, this represents general code quality / maintainability
        # (non-security logic bugs, code smells, and cosmetic warnings). We store the computed
        # `code_quality_score` into `HealthReport.duplication_score`.
        report_row = HealthReport(
            id=uuid.uuid4(),
            repository_id=repo_uuid,
            overall_score=int(round(overall_score)),
            complexity_score=int(round(complexity_score)),
            security_score=int(round(security_score)),
            duplication_score=int(round(raw_quality_score)),
            dependency_score=int(round(dependency_score)),
            metrics_json=metrics_json,
        )
        db.add(report_row)
        await db.commit()

        return {
            "health_report_id": str(report_row.id),
            "overall_score": int(round(overall_score)),
            "complexity_score": int(round(complexity_score)),
            "security_score": int(round(security_score)),
            "duplication_score": int(round(raw_quality_score)),
            "code_quality_score": int(round(raw_quality_score)),
            "dependency_score": int(round(dependency_score)),
            "metrics_json": metrics_json,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Task: Report Generation (Sprint 6)
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=1)
def report_generation_task(self, prev_result: dict) -> dict:
    """
    Stage 7: Compute Health Score and write health_report record.
    """
    job_id = prev_result["job_id"]
    repo_id = prev_result["repo_id"]
    log = logger.bind(task="report_generation", repo_id=repo_id, job_id=job_id)
    log.info("Starting Stage 7: report generation")

    _run_async(_update_job(job_id, "report_generation", STAGE_PROGRESS["report_generation"]))

    try:
        scores = _run_async(_generate_health_report(repo_id, job_id, prev_result, log))
        _run_async(_update_job(job_id, "done", 100))
        log.info("Report generation stage complete", **{k: v for k, v in scores.items() if k != "metrics_json"})

        # Clean up workspace directory after successful Stage 7 completion
        from app.config import get_settings
        settings = get_settings()
        workspace = prev_result.get("workspace") or str(Path(settings.clone_workspace_dir) / repo_id)
        freed_bytes = _cleanup_workspace(workspace, log)
        scores["workspace_freed_bytes"] = freed_bytes

        prev_result.update({"health_scores": scores})
        return prev_result
    except Exception as exc:
        log.error("Report generation stage failed", error=str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)
        raise


async def _get_latest_job_stage(repo_uuid: uuid.UUID) -> str | None:
    """Query the most recent indexing job stage for a repository."""
    from app.database import get_db_context
    from app.models import IndexingJob
    from sqlalchemy import select

    async with get_db_context() as db:
        stmt = (
            select(IndexingJob.stage)
            .where(IndexingJob.repository_id == repo_uuid)
            .order_by(IndexingJob.started_at.desc(), IndexingJob.id.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


@celery_app.task
def cleanup_stale_workspaces_task(max_age_hours: int = 24) -> dict:
    """
    Periodic TTL sweep: delete workspace directories older than `max_age_hours`.
    Prevents accumulation of orphaned workspaces from crashed or aborted tasks.

    Race-condition guard:
    Before deleting a workspace directory, query the indexing_jobs table for that
    repo_id's most recent job and skip deletion if its status is NOT a terminal state
    (i.e. status is anything other than "done" or "failed" — skip if it's still
    pending/cloning/parsing/building_graph/embedding/static_analysis). Only delete
    workspaces whose corresponding job has actually finished (successfully or not)
    AND is older than the age threshold. If no matching indexing_job row exists at all
    for a workspace directory (true orphan, e.g. from a deleted repository), it's safe
    to delete regardless of the job-status check.
    """
    from app.config import get_settings
    settings = get_settings()
    base_dir = Path(settings.clone_workspace_dir)
    if not base_dir.exists():
        return {"cleaned": 0, "total_freed_bytes": 0, "skipped_active": 0}

    import time
    now = time.time()
    cutoff = now - (max_age_hours * 3600)
    cleaned = 0
    total_freed = 0
    skipped_active = 0
    log = logger.bind(task="cleanup_stale_workspaces")

    TERMINAL_STAGES = {"done", "failed"}

    for entry in base_dir.iterdir():
        if entry.is_dir():
            try:
                if entry.stat().st_mtime < cutoff:
                    # Race-condition guard: check if corresponding repo job is still active
                    repo_uuid = None
                    try:
                        repo_uuid = uuid.UUID(entry.name)
                    except (ValueError, TypeError, AttributeError):
                        pass

                    if repo_uuid is not None:
                        try:
                            latest_stage = _run_async(_get_latest_job_stage(repo_uuid))
                        except Exception as db_exc:
                            log.warning(
                                "Failed to check indexing job status for workspace; skipping deletion for safety",
                                repo_id=entry.name,
                                error=str(db_exc),
                            )
                            skipped_active += 1
                            continue

                        if latest_stage is not None and latest_stage not in TERMINAL_STAGES:
                            log.info(
                                "Skipping workspace cleanup for active indexing job",
                                repo_id=entry.name,
                                stage=latest_stage,
                            )
                            skipped_active += 1
                            continue

                    freed = _cleanup_workspace(entry, log)
                    cleaned += 1
                    total_freed += freed
            except Exception as exc:
                log.warning("Error inspecting workspace directory", path=str(entry), error=str(exc))

    return {"cleaned": cleaned, "total_freed_bytes": total_freed, "skipped_active": skipped_active}


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
