# Roadmap & Sprint Plan
## DevLens AI — Solo Developer Execution Plan

**Document Version:** 1.0
**Assumption:** Solo developer, part-time or full-time equivalent of ~20–25 focused hours/week. Adjust sprint length if working full-time on this exclusively (roughly halve durations).

---

## 1. Version Roadmap (Refined)

| Version | Theme | Contains |
|---|---|---|
| **V1 (MVP)** | "Understand any codebase in 15 minutes" | Auth, GitHub import, Tree-sitter parsing, knowledge graph (tables), embeddings + semantic search, grounded AI chat, feature tracing, architecture diagram, health report |
| **V2** | "Deepen the intelligence" | Migrate graph to Neo4j, bug investigation from logs/stack traces, technical debt report, documentation generation, private repo support, GitLab import |
| **V3** | "Team & workflow integration" | PR review agent, GitHub App + CI/CD integration, team collaboration/permissions, repository comparison |
| **V4** | "Predictive engineering" | Regression prediction, AI-assisted refactoring suggestions, productivity analytics |

This preserves every capability from the original concept document — none were deleted, only sequenced.

---

## 2. V1 (MVP) Sprint Breakdown

**Total estimated duration: 10–12 weeks** at part-time pace (~20 hrs/week). Each sprint is 1 week.

### Sprint 1 — Foundations
- Repo scaffolding: Next.js frontend, FastAPI backend, Docker Compose (Postgres + Redis + pgvector)
- GitHub OAuth flow end-to-end (login, JWT issuance)
- Basic dashboard shell (empty state)
- **Exit criterion:** Can log in with GitHub and see an empty dashboard.

### Sprint 2 — Repository Import Pipeline (Part 1)
- Repository import endpoint, size/URL validation
- Celery + Redis job queue wired up
- Clone stage (shallow clone, sandboxed workspace, cleanup)
- Language detection stage
- Job status polling endpoint + frontend progress UI
- **Exit criterion:** Submitting a GitHub URL clones the repo and shows live stage progress.

### Sprint 3 — Code Parsing Engine
- Integrate `py-tree-sitter` with Python and JS/TS grammars
- Entity extraction: functions, classes, methods, imports, file-level metadata
- Store extracted entities in `files` + `graph_nodes` tables
- Handle parse failures gracefully (skip + log)
- **Exit criterion:** After import, `graph_nodes` table is populated correctly for a real test repo (verify manually against source).

### Sprint 4 — Knowledge Graph Construction
- Import resolution (map import statements to actual files/modules)
- Call resolution within statically resolvable scope
- `extends`/`implements` edge extraction (class inheritance)
- Recursive CTE traversal query implementation + tests
- **Exit criterion:** Can query "all callers of function X" and "shortest path between A and B" correctly on a test repo.

### Sprint 5 — Embeddings & Semantic Search
- Sentence-Transformers local embedding pipeline (or Voyage/Groq embedding API as fallback)
- Embedding generation stage in pipeline, pgvector storage
- Semantic search endpoint + top-K retrieval
- **Exit criterion:** Natural-language query like "JWT token creation" returns the correct function via `/search`.

### Sprint 6 — Static Analysis & Health Report
- Integrate Ruff, Bandit, ESLint as sandboxed subprocess runners
- Normalize tool output into `static_analysis_results`
- Implement Health Score formula (per HLD Section 6)
- Health report endpoint + frontend report view
- **Exit criterion:** Health report shows real, correct findings from actual tool output (not fabricated).

### Sprint 7 — AI Chat (RAG Pipeline)
- LLM provider abstraction (`LLMProvider` interface), Groq implementation first
- Retrieval pipeline: combine vector search + graph lookup into context assembly
- Prompt template with citation requirement enforced (FR-6.3)
- Chat endpoint + conversation persistence
- Frontend chat UI with clickable citations
- **Exit criterion:** Asking "What does this project do?" and "Where is X implemented?" on 3 test repos returns correct, cited answers.

### Sprint 8 — Feature Tracing
- Entry-point identification via semantic search
- Path construction via graph BFS/shortest-path from entry point toward likely terminal nodes (DB access, external API calls)
- Confidence/completeness scoring
- Frontend trace view (ordered list + path diagram)
- **Exit criterion:** "Trace the login flow" produces a correct, ordered path on at least 2 of 3 test repos.

### Sprint 9 — Architecture Visualization
- Component aggregation logic (group files/nodes into logical modules using directory structure + import density heuristics)
- Architecture endpoint
- Frontend Mermaid.js/react-flow rendering with click-to-detail
- **Exit criterion:** Diagram is generated from real graph data and roughly matches the repo's actual module structure on manual inspection.

### Sprint 10 — Dashboard Polish & Cross-Cutting Concerns
- Repository list/summary cards, delete/reindex flows
- Rate limiting middleware
- Error handling and user-facing error states across all flows
- Sentry integration, basic logging/observability
- **Exit criterion:** All FR/NFR items in the SRS marked "Must" are demonstrably satisfied.

### Sprint 11 — Testing & Hardening
- End-to-end test pass across 3 reference repositories (small/medium/large per SRS Section 7)
- Load-test the pipeline for the 15-minute budget (NFR-1)
- Security review: sandbox isolation check, secret handling audit
- Bug fixing buffer

### Sprint 12 — Deployment & Launch Prep
- Production Docker Compose on Oracle Always Free VM
- Domain + HTTPS (Let's Encrypt via Nginx/Certbot)
- Frontend deploy to Vercel
- README, demo video, portfolio write-up
- **Exit criterion:** Public MVP is live and passes the Section 6 success criteria from the Project Charter.

---

## 3. V2 Sprint Themes (Not Detailed Yet — Plan When Scheduled)
1. Neo4j migration for the graph layer
2. Bug Investigation Agent (log/stack trace correlation with graph + recent commits)
3. Technical Debt Agent (long methods, circular dependencies, duplicate logic, stale dependencies)
4. Documentation Agent (README/API docs/sequence diagram generation)
5. Private repository support (expanded OAuth scopes, per-repo access tokens)
6. GitLab import

## 4. V3 Sprint Themes
1. Pull Request Review Agent (performance, security, maintainability, test coverage, naming)
2. GitHub App + CI/CD webhook integration (auto re-index on push, PR comments)
3. Team accounts, roles, shared repository access
4. Repository comparison (diff two repos' architecture/health)

## 5. V4 Sprint Themes
1. Regression risk prediction (correlate historical bugs with code change patterns)
2. AI-assisted refactoring suggestions grounded in the graph
3. Engineering productivity analytics dashboard

---

## 6. Milestone Demo Checklist (Use at End of Sprint 12)

- [ ] Import a public repo end-to-end within 15 minutes
- [ ] Ask 5 prepared questions in chat, all answered with correct citations
- [ ] Run 1 feature trace successfully
- [ ] View architecture diagram matching real structure
- [ ] View health report with real static analysis findings
- [ ] Delete a repository and confirm all derived data is removed
- [ ] Full flow works on 3 repos of different sizes/languages
