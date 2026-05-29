/**
 * Typed API client for the AW Compliance Intelligence backend.
 * JWT auth: token + email persisted in localStorage. On 401, clears both
 * and bounces the browser to /login.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "aw_token";
const EMAIL_KEY = "aw_email";

// ── Types — mirror backend Pydantic models ────────────────────────────────

export type DocType =
  | "inspection_report"
  | "regulation"
  | "policy"
  | "enforcement_action";

export type Source = "USDA_APHIS" | "CFR_Title9" | "APHIS_Enforcement";

export type ViolationCategory =
  | "overcrowding"
  | "veterinary_care"
  | "transport_conditions"
  | "sanitation"
  | "water_access"
  | "euthanasia"
  | "housing"
  | "feeding"
  | "handling"
  | "recordkeeping";

export interface SearchRequest {
  /** Empty/missing query triggers filter-only mode on the backend. */
  query?: string;
  top_k?: number;
  doc_type?: DocType;
  source?: Source;
  categories?: ViolationCategory[];
  jurisdiction?: string;
  facility_name?: string;
  species?: string[];
  inspector_name?: string;
  reference_number?: string;
  date_from?: string;
  date_to?: string;
  include_parents?: boolean;
  vector_weight?: number;
  bm25_weight?: number;
  metadata_weight?: number;
}

export interface ScoreBreakdown {
  vector_score: number;
  bm25_score: number;
  metadata_boost: number;
  final_score: number;
}

export interface SearchResultMetadata {
  issuer?: string | null;
  jurisdiction?: string | null;
  facility_name?: string | null;
  species?: string[] | null;
  inspection_date?: string | null;
  inspector_name?: string | null;
  reference_number?: string | null;
  categories?: string[] | null;
  extra?: Record<string, unknown> | null;
}

export interface SearchResult {
  id: string;
  original_name: string;
  doc_type: DocType | null;
  source: string | null;
  retrieval_summary: string | null;
  parent_document_id: string | null;
  metadata: SearchResultMetadata | null;
  scores: ScoreBreakdown;
  match_reason: string | null;
}

export interface SearchResponse {
  query: string;
  total_results: number;
  results: SearchResult[];
}

export interface DocumentMetadata {
  id: string;
  document_id: string;
  issuer?: string | null;
  jurisdiction?: string | null;
  facility_name?: string | null;
  species?: string[] | null;
  inspection_date?: string | null;
  inspector_name?: string | null;
  reference_number?: string | null;
  categories?: string[] | null;
  extra?: Record<string, unknown> | null;
}

export interface DocumentResponse {
  id: string;
  filename: string;
  original_name: string;
  file_path: string;
  file_size?: number | null;
  mime_type?: string | null;
  status: string;
  error_message?: string | null;
  doc_type?: string | null;
  source?: string | null;
  retrieval_summary?: string | null;
  ingested_by?: string | null;
  parent_document_id?: string | null;
  /** 1-indexed PDF page range for split-section children; null for root docs. */
  page_start?: number | null;
  page_end?: number | null;
  created_at: string;
  updated_at: string;
  metadata?: DocumentMetadata | null;
}

export interface DocumentUrlResponse {
  url: string;
  expires_in: number;
}

export interface DocumentListParams {
  page?: number;
  page_size?: number;
  status?: string;
  doc_type?: DocType;
  source?: Source;
  parent_id?: string;
  include_parents?: boolean;
}

export interface DocumentListResponse {
  items: DocumentResponse[];
  total: number;
  page: number;
  page_size: number;
}

// ── Chat (Phase 6) ────────────────────────────────────────────────────────

export interface Citation {
  cit_id: number;
  document_id: string;
  section: string | null;
  snippet: string;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations: Citation[] | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  user_id: string;
  scope_type: "document" | "result_set";
  scope_document_id: string | null;
  scope_query: string | null;
  scope_filters: Record<string, unknown> | null;
  title: string | null;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}

export interface CreateConversationParams {
  scope_type: "document" | "result_set";
  scope_document_id?: string;
  scope_query?: string;
  scope_filters?: Record<string, unknown>;
}

export type ChatStreamEvent =
  | { event: "token"; data: { delta: string } }
  | { event: "citations"; data: Citation[] }
  | { event: "done"; data: { message_id: string } }
  | { event: "error"; data: { detail: string } };

export interface ConversationListItem {
  id: string;
  scope_type: "document" | "result_set";
  scope_document_id: string | null;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  scope_doc_type: string | null;
  scope_doc_original_name: string | null;
  scope_doc_facility_name: string | null;
  scope_doc_jurisdiction: string | null;
}

export interface ConversationListResponse {
  items: ConversationListItem[];
  total: number;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

/**
 * Extract a user-friendly message from the backend error JSON shape:
 *   {"error": {"code": "...", "message": "...", "request_id": "..."}}
 * Falls back to legacy {detail: ...} (FastAPI default) and finally statusText.
 */
function extractErrorMessage(body: unknown, statusText: string): string {
  if (body && typeof body === "object") {
    const b = body as Record<string, unknown>;
    if (b.error && typeof b.error === "object" && b.error !== null) {
      const e = b.error as Record<string, unknown>;
      if (typeof e.message === "string") return e.message;
    }
    if (typeof b.detail === "string") return b.detail;
  }
  return statusText || "Request failed";
}

// ── Token / session handling ──────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getStoredEmail(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(EMAIL_KEY);
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(EMAIL_KEY);
}

function storeSession(token: string, email: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(EMAIL_KEY, email);
}

function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  const here = window.location.pathname + window.location.search;
  const next = here && here !== "/login" ? `?next=${encodeURIComponent(here)}` : "";
  window.location.replace(`/login${next}`);
}

// ── Core request helper ───────────────────────────────────────────────────

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  if (!token) {
    redirectToLogin();
    throw new ApiError(401, "Not authenticated");
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
  });

  if (res.status === 401) {
    clearSession();
    redirectToLogin();
    throw new ApiError(401, "Session expired");
  }

  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    throw new ApiError(res.status, extractErrorMessage(body, res.statusText), body);
  }
  return (await res.json()) as T;
}

// ── Endpoints ──────────────────────────────────────────────────────────────

/**
 * Log in directly against /api/auth/login. Does not use the authed
 * `request` helper since the user has no token yet.
 */
export async function login(email: string, password: string): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    const detail = extractErrorMessage(body, res.statusText);
    throw new ApiError(res.status, detail, body);
  }
  const data = (await res.json()) as TokenResponse;
  storeSession(data.access_token, email);
  return data;
}

export async function search(req: SearchRequest): Promise<SearchResponse> {
  return request<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getDocument(id: string): Promise<DocumentResponse> {
  return request<DocumentResponse>(`/api/documents/${id}`);
}

export async function getDocumentUrl(id: string): Promise<DocumentUrlResponse> {
  return request<DocumentUrlResponse>(`/api/documents/${id}/url`);
}

export async function listDocuments(
  params: DocumentListParams = {},
): Promise<DocumentListResponse> {
  const qs = new URLSearchParams();
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  if (params.status) qs.set("status", params.status);
  if (params.doc_type) qs.set("doc_type", params.doc_type);
  if (params.source) qs.set("source", params.source);
  if (params.parent_id) qs.set("parent_id", params.parent_id);
  if (params.include_parents) qs.set("include_parents", "true");
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request<DocumentListResponse>(`/api/documents${suffix}`);
}

// ── Chat endpoints ────────────────────────────────────────────────────────

export async function createConversation(
  params: CreateConversationParams,
): Promise<Conversation> {
  return request<Conversation>("/api/chat/conversations", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function getConversation(id: string): Promise<Conversation> {
  return request<Conversation>(`/api/chat/conversations/${id}`);
}

export async function listConversations(
  page = 1,
  page_size = 20,
): Promise<ConversationListResponse> {
  const qs = new URLSearchParams();
  qs.set("page", String(page));
  qs.set("page_size", String(page_size));
  return request<ConversationListResponse>(`/api/chat/conversations?${qs}`);
}

/**
 * Stream a message via SSE. Calls onEvent for each parsed event.
 * Returns when the stream closes (done or error event, or stream ends).
 * Throws if the initial POST fails (e.g. auth, scope errors).
 */
export async function streamMessage(
  conversationId: string,
  content: string,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken();
  if (!token) {
    redirectToLogin();
    throw new ApiError(401, "Not authenticated");
  }

  const res = await fetch(
    `${API_BASE}/api/chat/conversations/${conversationId}/messages`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ content }),
      signal,
    },
  );

  if (res.status === 401) {
    clearSession();
    redirectToLogin();
    throw new ApiError(401, "Session expired");
  }

  if (!res.ok || !res.body) {
    let body: unknown;
    try { body = await res.json(); } catch { body = await res.text(); }
    throw new ApiError(res.status, extractErrorMessage(body, res.statusText), body);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by a blank line. An event has the form:
    //   event: <name>\n
    //   data: <json>\n
    //   \n
    let sepIdx: number;
    while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, sepIdx);
      buffer = buffer.slice(sepIdx + 2);
      const parsed = parseSseEvent(raw);
      if (parsed) onEvent(parsed);
    }
  }
}

function parseSseEvent(raw: string): ChatStreamEvent | null {
  let eventName = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event: ")) eventName = line.slice(7).trim();
    else if (line.startsWith("data: ")) dataLines.push(line.slice(6));
  }
  if (dataLines.length === 0) return null;
  try {
    const data = JSON.parse(dataLines.join("\n"));
    if (eventName === "token" || eventName === "citations" || eventName === "done" || eventName === "error") {
      return { event: eventName, data } as ChatStreamEvent;
    }
  } catch {
    return null;
  }
  return null;
}
