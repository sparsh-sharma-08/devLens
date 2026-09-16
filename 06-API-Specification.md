# API Specification
## DevLens AI V1 — REST API

**Document Version:** 1.0
**Base URL (example):** `https://api.devlens.ai/v1`
**Auth:** Bearer JWT in `Authorization` header for all endpoints except `/auth/*`

---

## 1. Authentication

### `GET /auth/github/login`
Redirects to GitHub OAuth consent screen.

### `GET /auth/github/callback`
Handles OAuth callback, creates/updates user, returns session.
**Response 200:**
```json
{ "access_token": "jwt...", "refresh_token": "jwt...", "user": { "id": "uuid", "username": "octocat", "avatar_url": "..." } }
```

### `POST /auth/refresh`
**Body:** `{ "refresh_token": "jwt..." }`
**Response 200:** `{ "access_token": "jwt..." }`

### `POST /auth/logout`
Invalidates the current refresh token.
**Response 204**

---

## 2. Repositories

### `POST /repositories`
Import a new repository.
**Body:**
```json
{ "source_url": "https://github.com/owner/repo" }
```
**Response 202 (Accepted — processing started):**
```json
{ "repository_id": "uuid", "job_id": "uuid", "status": "pending" }
```
**Errors:** `400` invalid URL, `409` repository exceeds size limit, `422` repository already imported by this user.

### `GET /repositories`
List repositories owned by the current user.
**Response 200:**
```json
{
  "repositories": [
    { "id": "uuid", "name": "repo", "primary_language": "Python", "health_score": 82, "status": "ready", "last_indexed_at": "2026-07-01T12:00:00Z" }
  ]
}
```

### `GET /repositories/{repository_id}`
**Response 200:** Full repository detail including metadata, current status, health score.

### `DELETE /repositories/{repository_id}`
Deletes repository and all derived data (NFR-13).
**Response 204**

### `POST /repositories/{repository_id}/reindex`
Re-triggers the processing pipeline.
**Response 202:** `{ "job_id": "uuid" }`

---

## 3. Indexing Job Status

### `GET /jobs/{job_id}`
Poll for pipeline progress (FR-2.6).
**Response 200:**
```json
{
  "job_id": "uuid",
  "repository_id": "uuid",
  "stage": "building_graph",
  "progress_pct": 55,
  "error_message": null
}
```

---

## 4. Knowledge Graph

### `GET /repositories/{repository_id}/graph`
Returns the full (or paginated, for large repos) graph for visualization.
**Query params:** `node_type` (filter, optional), `max_nodes` (default 300)
**Response 200:**
```json
{
  "nodes": [ { "id": "uuid", "name": "AuthService", "node_type": "class", "file_path": "src/auth/service.py" } ],
  "edges": [ { "source": "uuid", "target": "uuid", "edge_type": "calls" } ]
}
```

### `GET /repositories/{repository_id}/graph/nodes/{node_id}`
Detail view of one node: signature, docstring, direct neighbors.

---

## 5. Semantic Search

### `GET /repositories/{repository_id}/search?q={query}`
**Response 200:**
```json
{
  "results": [
    { "node_id": "uuid", "name": "create_jwt_token", "file_path": "src/auth/jwt.py", "line": 42, "score": 0.87 }
  ]
}
```

---

## 6. AI Chat

### `POST /repositories/{repository_id}/chat`
**Body:**
```json
{ "conversation_id": "uuid | null", "message": "Where are JWT tokens created?" }
```
**Response 200:**
```json
{
  "conversation_id": "uuid",
  "message": {
    "role": "assistant",
    "content": "JWT tokens are created in `create_jwt_token` (src/auth/jwt.py:42), called from `AuthService.login`...",
    "citations": [
      { "node_id": "uuid", "file_path": "src/auth/jwt.py", "start_line": 42, "end_line": 58 }
    ]
  }
}
```

### `GET /repositories/{repository_id}/chat/conversations`
List past conversations for this repository (current user only).

### `GET /chat/conversations/{conversation_id}/messages`
Full message history for a conversation.

---

## 7. Feature Tracing

### `POST /repositories/{repository_id}/trace`
**Body:** `{ "description": "login flow" }`
**Response 200:**
```json
{
  "steps": [
    { "order": 1, "node_id": "uuid", "name": "LoginForm", "file_path": "frontend/LoginForm.tsx", "role": "entry_point" },
    { "order": 2, "node_id": "uuid", "name": "AuthController.login", "file_path": "src/auth/controller.py", "role": "handler" },
    { "order": 3, "node_id": "uuid", "name": "AuthService.authenticate", "file_path": "src/auth/service.py", "role": "business_logic" },
    { "order": 4, "node_id": "uuid", "name": "UserRepository.find_by_username", "file_path": "src/db/user_repo.py", "role": "data_access" }
  ],
  "confidence": "4 of an estimated 5 steps found",
  "completeness_pct": 80
}
```

---

## 8. Architecture Diagram

### `GET /repositories/{repository_id}/architecture`
Returns a module/component-level abstraction of the graph, pre-aggregated for diagram rendering.
**Response 200:**
```json
{
  "components": [ { "id": "auth", "label": "Auth Module", "files": ["src/auth/service.py", "src/auth/jwt.py"] } ],
  "relationships": [ { "from": "auth", "to": "database", "type": "depends_on" } ]
}
```

---

## 9. Health Report

### `GET /repositories/{repository_id}/health`
**Response 200:**
```json
{
  "overall_score": 82,
  "complexity_score": 78,
  "security_score": 90,
  "duplication_score": 85,
  "dependency_score": 75,
  "top_issues": [
    { "severity": "high", "tool": "bandit", "message": "Use of eval() detected", "file_path": "src/utils/parser.py", "line": 112 }
  ],
  "generated_at": "2026-07-01T12:10:00Z"
}
```

---

## 10. Error Format (All Endpoints)

```json
{
  "error": {
    "code": "REPOSITORY_TOO_LARGE",
    "message": "This repository exceeds the 50,000 LOC limit for the current tier.",
    "status": 409
  }
}
```

Standard HTTP status codes are used throughout: `200` success, `202` accepted/async, `204` no content, `400` bad request, `401` unauthorized, `403` forbidden, `404` not found, `409` conflict, `422` unprocessable, `500` server error.

---

## 11. Rate Limiting (NFR alignment)

All endpoints are rate-limited per user (default: 60 requests/minute for read endpoints, 5 imports/hour for `POST /repositories`, 20 messages/hour for `/chat` on the free tier) to stay within free-tier LLM/compute budgets. Limits are configurable per deployment.
