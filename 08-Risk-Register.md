# Risk Register
## DevLens AI — MVP

**Document Version:** 1.0

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-1 | Tree-sitter call/import resolution is incomplete for dynamic language features (e.g., Python's dynamic imports, JS's dynamic `require`), producing an inaccurate graph | High | Medium | Attach a `confidence` score to edges (per DB design); communicate uncertainty in UI rather than presenting guesses as fact; scope V1 accuracy expectations honestly in demo |
| R-2 | Free-tier LLM inference (Groq) has rate limits that throttle demo/early usage | Medium | Medium | Abstract LLM provider behind an interface; add response caching for repeated questions; keep a paid-provider fallback path ready but optional |
| R-3 | Oracle Always Free VM approval/availability is inconsistent by region/account | Medium | High | Have Fly.io free allowance as a documented fallback deployment target from day one |
| R-4 | Repository processing exceeds the 15-minute budget on larger/more complex repos | Medium | Medium | Enforce the 50k LOC ceiling (FR-2.4); parallelize independent pipeline stages where possible; make the limit configurable and clearly communicated to users |
| R-5 | Malicious code in an imported repository attempts to execute during processing | Low | Critical | Static-only parsing (no code execution); sandboxed, network-isolated containers for cloning/analysis (NFR-5) |
| R-6 | Solo-developer scope creep — reintroducing V2/V3/V4 features into V1 mid-build | High | High | This document set (Charter, SRS, Roadmap) exists specifically to prevent this; treat Section 8 of the SRS ("Deferred Requirements") as a hard boundary |
| R-7 | Supabase free tier pauses the database after inactivity, breaking demo availability | Medium | Low | Use a lightweight scheduled keep-alive ping, or self-host Postgres on the same Oracle VM instead of relying on Supabase's pause-prone free tier |
| R-8 | pgvector performance degrades at higher embedding volumes without a proper ANN index | Low | Medium | Use `ivfflat`/`hnsw` indexes from the start (per DB design); monitor query latency; migrate to dedicated Qdrant only if needed |
| R-9 | Health Score formula is perceived as arbitrary/unfair by users | Medium | Low | Document the formula transparently (HLD Section 6) and expose raw metrics alongside the composite score |
| R-10 | GitHub API rate limits affect metadata fetching for popular/large repos | Low | Low | Use authenticated requests (higher rate limit tier) and cache repository metadata between re-indexes |
