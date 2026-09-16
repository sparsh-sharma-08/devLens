/**
 * DevLens AI — API Client
 * Centralized HTTP client with auth token injection.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/v1";

// ── Token management ─────────────────────────────────────────────────────────

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("devlens_access_token");
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("devlens_refresh_token");
}

export function setTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem("devlens_access_token", accessToken);
  localStorage.setItem("devlens_refresh_token", refreshToken);
}

export function clearTokens() {
  localStorage.removeItem("devlens_access_token");
  localStorage.removeItem("devlens_refresh_token");
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────

class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  // Auto-refresh on 401
  if (res.status === 401 && retry) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      return apiFetch<T>(path, options, false);
    } else {
      clearTokens();
      window.location.href = "/";
      throw new ApiError(401, "UNAUTHORIZED", "Session expired");
    }
  }

  if (!res.ok) {
    let errorBody: any = {};
    try {
      errorBody = await res.json();
    } catch {}
    // FastAPI throws {"detail": "..."} for HTTPExceptions
    // Our custom handler wraps as {"error": {"code": "...", "message": "..."}}
    const err = errorBody?.error || {};
    const message =
      err.message ||
      (typeof errorBody?.detail === "string" ? errorBody.detail : null) ||
      res.statusText;
    throw new ApiError(res.status, err.code || "API_ERROR", message);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

async function tryRefreshToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    setTokens(data.access_token, refreshToken);
    return true;
  } catch {
    return false;
  }
}

// ── API methods ───────────────────────────────────────────────────────────────

export const api = {
  // Auth
  auth: {
    loginWithGitHub: () => {
      window.location.href = `${API_BASE}/auth/github/login`;
    },
    loginWithGoogle: () => {
      window.location.href = `${API_BASE}/auth/google/login`;
    },
    signup: (username: string, email: string, password: string) =>
      apiFetch<TokenResponse>("/auth/signup", {
        method: "POST",
        body: JSON.stringify({ username, email, password }),
      }),
    login: (email: string, password: string) =>
      apiFetch<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    logout: () => apiFetch("/auth/logout", { method: "POST" }),
    refresh: (refreshToken: string) =>
      apiFetch<{ access_token: string }>("/auth/refresh", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refreshToken }),
      }),
  },

  // Repositories
  repos: {
    list: () => apiFetch<{ repositories: Repository[] }>("/repositories"),
    get: (id: string) => apiFetch<Repository>(`/repositories/${id}`),
    import: (sourceUrl: string) =>
      apiFetch<{ repository_id: string; job_id: string; status: string }>("/repositories", {
        method: "POST",
        body: JSON.stringify({ source_url: sourceUrl }),
      }),
    delete: (id: string) => apiFetch<void>(`/repositories/${id}`, { method: "DELETE" }),
    reindex: (id: string) =>
      apiFetch<{ job_id: string }>(`/repositories/${id}/reindex`, { method: "POST" }),
  },

  // Jobs
  jobs: {
    status: (jobId: string) => apiFetch<JobStatus>(`/jobs/${jobId}`),
  },

  // Graph
  graph: {
    get: (repoId: string, maxNodes?: number) =>
      apiFetch<GraphData>(`/repositories/${repoId}/graph${maxNodes ? `?max_nodes=${maxNodes}` : ""}`),
    getNode: (repoId: string, nodeId: string) =>
      apiFetch<GraphNode>(`/repositories/${repoId}/graph/nodes/${nodeId}`),
  },

  // Search
  search: {
    semantic: (repoId: string, query: string) =>
      apiFetch<{ results: SearchResult[] }>(`/repositories/${repoId}/search?q=${encodeURIComponent(query)}`),
  },

  // Chat
  chat: {
    send: (repoId: string, message: string, conversationId?: string) =>
      apiFetch<ChatResponse>(`/repositories/${repoId}/chat`, {
        method: "POST",
        body: JSON.stringify({ conversation_id: conversationId ?? null, message }),
      }),
    listConversations: (repoId: string) =>
      apiFetch<{ conversations: Conversation[] }>(`/repositories/${repoId}/chat/conversations`),
    getMessages: (conversationId: string) =>
      apiFetch<{ messages: ChatMessage[] }>(`/chat/conversations/${conversationId}/messages`),
  },

  // Feature Tracing
  trace: {
    run: (repoId: string, description: string) =>
      apiFetch<TraceResult>(`/repositories/${repoId}/trace`, {
        method: "POST",
        body: JSON.stringify({ description }),
      }),
  },

  // Architecture
  architecture: {
    get: (repoId: string) =>
      apiFetch<ArchitectureData>(`/repositories/${repoId}/architecture`),
  },

  // Health Report
  health: {
    get: (repoId: string) =>
      apiFetch<HealthReport>(`/repositories/${repoId}/health`),
  },
};

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Repository {
  id: string;
  name: string;
  full_name: string;
  source_url: string;
  primary_language: string | null;
  health_score: number | null;
  status: "pending" | "indexing" | "ready" | "failed";
  last_indexed_at: string | null;
  created_at: string;
}

export interface JobStatus {
  job_id: string;
  repository_id: string;
  stage: string;
  progress_pct: number;
  error_message: string | null;
}

export interface GraphNode {
  id: string;
  name: string;
  node_type: string;
  file_path?: string;
  qualified_name?: string;
  start_line?: number;
  end_line?: number;
  signature?: string;
  docstring?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  edge_type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface SearchResult {
  node_id: string;
  name: string;
  file_path: string;
  line: number;
  score: number;
}

export interface Citation {
  node_id: string;
  file_path: string;
  start_line: number;
  end_line: number;
}

export interface ChatMessage {
  id?: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  created_at?: string;
}

export interface ChatResponse {
  conversation_id: string;
  message: ChatMessage;
}

export interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
}

export interface TraceStep {
  order: number;
  node_id: string;
  name: string;
  file_path: string;
  role: string;
}

export interface TraceResult {
  steps: TraceStep[];
  confidence: string;
  completeness_pct: number;
}

export interface ArchitectureData {
  components: { id: string; label: string; files: string[] }[];
  relationships: { from: string; to: string; type: string }[];
}

export interface HealthReport {
  overall_score: number;
  complexity_score: number;
  security_score: number;
  duplication_score: number;
  dependency_score: number;
  top_issues: {
    severity: string;
    tool: string;
    message: string;
    file_path: string;
    line: number;
  }[];
  generated_at: string;
}

export interface User {
  id: string;
  username: string;
  avatar_url: string | null;
  email: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}
