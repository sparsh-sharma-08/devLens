# DevLens AI — Screenshot Assets

This directory contains visual assets and screenshots referenced in the root [`README.md`](../../README.md).

## Asset Inventory

| Filename | Description | Status |
|---|---|---|
| `hero-banner.jpg` | High-resolution visual identity header and tagline banner (1920x1080) | ✅ Present |
| `dashboard.png` | Repository dashboard with repository cards, health ratings, and import trigger | 📷 To capture |
| `import-pipeline.png` | Live 7-stage Celery indexing pipeline progress modal (5% -> 100%) | 📷 To capture |
| `repo-health.png` | 4-pillar health report gauges, ceiling verification, and security findings table | 📷 To capture |
| `architecture-graph.png` | Interactive architecture graph generated from AST imports and call edges | 📷 To capture |
| `feature-trace.png` | End-to-end execution trace with lifecycle roles (entry point, handler, logic) | 📷 To capture |
| `grounded-chat.png` | Grounded AI conversation interface with exact file/line citation chips | 📷 To capture |

## Capture Instructions

When running the application locally (`docker compose up -d` and `cd frontend && npm run dev`):

1. **Dashboard (`dashboard.png`)**: Navigate to `http://localhost:3000/dashboard` and capture the repository overview showing indexed repositories like `encode/httpx`.
2. **Indexing Pipeline (`import-pipeline.png`)**: Click **Import Repository**, paste a repository URL (e.g. `https://github.com/encode/httpx`), and capture the live multi-stage progress modal.
3. **Health Report (`repo-health.png`)**: Click into `encode/httpx` > **Health** tab. Capture the composite score gauge (94/100), the 4 pillar cards (Security 97, Code Quality 94, Complexity 99, Dependencies 77), and the issue findings list.
4. **Architecture (`architecture-graph.png`)**: Select the **Architecture** tab. Capture the rendered Mermaid/React Flow module dependency graph.
5. **Feature Trace (`feature-trace.png`)**: Select the **Trace** tab. Enter `"HTTP request dispatch"`, click **Trace**, and capture the sequenced step cards with role pills.
6. **Grounded Chat (`grounded-chat.png`)**: Select the **Chat** tab. Ask `"How does HTTPX send an asynchronous request?"` and capture the markdown response with clickable citation chips.

*Recommended dimensions:* 1920x1080 or 1440x900, PNG format, compressed with `pngquant` or lossless tools.
