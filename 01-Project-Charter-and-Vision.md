# DevLens AI — Project Charter & Refined Vision

**Document Type:** Project Charter
**Version:** 1.0 (Refined MVP Scope)
**Status:** Approved for Build

---

## 1. Tagline

> **"Understand any codebase in 15 minutes."**

This replaces the broader original tagline ("Understand. Analyze. Improve. Every Codebase.") as the *single measurable promise* the MVP must deliver. Everything in V1 is chosen because it serves this promise directly.

---

## 2. Why the Scope Was Narrowed

The original concept document lists 8 major components, 8 AI agents, and a V1–V4 roadmap that collectively describe a Series-A-funded team's multi-year product — not a solo, zero-budget build. Attempting all of it in the first version produces a shallow demo instead of a deep, working product.

**Refinement principle:** Ship a narrow product that is *fully real* (real parsing, real graph, real retrieval, real answers) rather than a broad product that is *fully fake* (regex-based "parsing," keyword search dressed up as "semantic," canned answers).

The refined MVP keeps exactly seven capabilities, all traceable to the core promise:

| # | Capability | Why it's in the MVP |
|---|---|---|
| 1 | Repository ingestion & indexing | Without this, nothing else exists |
| 2 | Code-aware parsing (Tree-sitter + AST) | This is DevLens's actual differentiator vs. "chunk and embed" tools |
| 3 | Engineering Knowledge Graph (lightweight) | Grounds every AI answer in real structure, not just vector similarity |
| 4 | Natural-language Q&A (RAG, graph-grounded) | The core interactive experience |
| 5 | Feature tracing | The single most impressive, demo-able capability |
| 6 | Architecture visualization | Makes the graph tangible and interview-worthy |
| 7 | Repository health report | Turns static analysis into a shareable, scorable artifact |

Everything else from the original document — PR review, bug investigation from logs, documentation generation, CI/CD integration, team collaboration, predictive analytics — is preserved in the roadmap (see `07-Roadmap-and-Sprint-Plan.md`) as **V2/V3/V4**, not discarded.

---

## 3. Problem Statement (Unchanged, Retained From Original)

Modern software projects span tens of thousands to millions of lines of code across hundreds of files. Developers struggle with:

- Understanding unfamiliar codebases
- Long onboarding times
- Tracing feature implementations end-to-end
- Debugging complex, cross-service systems
- Identifying technical debt
- Keeping documentation synchronized with code
- Reviewing pull requests efficiently
- Understanding overall software architecture
- Finding performance bottlenecks
- Retaining engineering knowledge as teams change

Existing AI coding assistants (Copilot-style tools) are optimized for **code generation**, not **repository comprehension**. They have no persistent, structural model of the codebase they're working in. DevLens AI's differentiation is a **persistent, queryable model of the repository** — a graph, not just a context window.

---

## 4. Core Philosophy (Unchanged)

DevLens does not "read files and summarize." It builds a **Engineering Knowledge Graph** representing:

- Source code entities (functions, classes, modules)
- Relationships (calls, imports, extends, implements, depends-on)
- Documentation
- Dependencies
- APIs / routes
- Data flow between components

Every AI response is **grounded in this graph** — retrieval pulls structured facts from the graph *and* semantically relevant text from embeddings, then the LLM reasons over both. This is what separates DevLens from "RAG over chunked files."

---

## 5. Target Users (Unchanged)

| User | Primary Need |
|---|---|
| Students | Understand open-source repos they didn't write |
| Developers | Ramp up on unfamiliar codebases fast |
| Engineering teams | Onboarding and tribal-knowledge retention |
| Startups | Keep documentation from rotting |
| Enterprises | Repository-level intelligence at scale (post-MVP) |

For the MVP, **design for one persona only: a mid-level developer joining an existing project.** This keeps every UX decision concrete. Student/enterprise needs are served by V2+.

---

## 6. MVP Success Criteria

The MVP is "done" when a developer can:

1. Paste a public GitHub URL and get a fully indexed, browsable repository within ~15 minutes for a repo up to ~50k LOC.
2. Ask "What does this project do?" and "Where is X implemented?" and get an answer that cites actual files/functions (not hallucinated).
3. Ask to "trace" a feature (e.g., "show me the login flow") and see an ordered, clickable path through real files/functions.
4. View an architecture diagram generated from the actual graph, not a static template.
5. View a health report with at least 4 real metrics (complexity, duplication, security findings, dependency staleness) computed by real tools, not guessed by the LLM.

If a feature can't meet these bars honestly, it stays out of the MVP.

---

## 7. Why This Project Matters (Retained, Reframed for Portfolio Use)

A well-executed DevLens AI MVP demonstrates:

- Static analysis & AST/Tree-sitter tooling
- Graph modeling and graph-based reasoning
- Retrieval-Augmented Generation done properly (structured + semantic retrieval, not naive chunking)
- Full-stack engineering (Next.js + FastAPI + background job processing)
- Data modeling for a non-trivial multi-entity domain
- Visualization of derived, computed data
- Free-tier production deployment and basic observability

This is a stronger interview/portfolio artifact than a broader but shallower build, because every claim in the demo is backed by something real happening under the hood.
