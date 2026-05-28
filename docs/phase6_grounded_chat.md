# Phase 6: Grounded Document Chat

A scoped conversational interface over the USDA APHIS corpus. Every answer is bounded to a single document, cites the specific passages it draws from, and is guarded against the three behaviors that would compromise the platform's investigative integrity: drawing legal conclusions, making unsupported claims, and presenting findings as established fact.

---

## Overview

```
/documents/[id]    "Ask about this document" → slide-in chat panel (480px)
/chat              Past conversations list, joined with their scope document
/chat/[id]         Standalone thread view with citation pills + continue
```

Both the embedded panel and the standalone thread use the same backend pipeline. Streaming via Server-Sent Events delivers token-by-token responses so long answers don't feel frozen.

---

## The Three Hard Constraints

These are non-negotiable behaviors enforced in three layers:

1. **No legal conclusions** — never declare a violation, never label as compliant or non-compliant, never render a verdict.
2. **No unsupported claims** — if the retrieved passages don't answer the question, say so explicitly.
3. **Observational framing only** — "the report notes…", "the inspector documented…", never as established fact.

### Defense in depth

| Layer | Enforcement |
|---|---|
| **Prompt** | `SYSTEM_PROMPT` in `app/chat/rag.py` encodes all three rules in absolute terms with examples of observational language and explicit refusal patterns. |
| **Retrieval bounding** | Passages come exclusively from the scope document's `raw_text`. The model has no access to other documents — it cannot fabricate references it wasn't shown. |
| **Response validation** | `parse_citations()` resolves every `[CIT-N]` marker against the actual passages and discards unresolvable ones. `detect_verdict_language()` regex-scans the response for verdict phrases ("is a violation", "guilty of", "non-compliant", etc.) and logs warnings. |

The combination means failures that *can* happen (the model trying to draw a soft conclusion under user pressure) show up as visible refusals or logged warnings rather than silent misinformation. Loud failures are recoverable; silent ones are exactly what these constraints exist to prevent.

---

## Backend Pipeline

### 1. Passage prep

`app/chat/rag.py — _split_into_passages()` takes the document's `raw_text` and splits it into ~2500-character passages, preferring paragraph boundaries. A regex-based heuristic detects section headers (lines that look like `§3.131(c)` or short ALL-CAPS strings) and uses them as labels — e.g. `[CIT-3] (Section: §2.40)`. Passages shorter than 200 chars are dropped. Up to 30 passages per document.

Pages are not real PDF page numbers (we don't have a coord→page map yet — deferred). Section labels are the citation anchor; for passages without a detected section header, the fallback is `Passage N`.

### 2. Prompt construction

`_build_messages()` assembles the LLM message list:

```
system: SYSTEM_PROMPT                        (the three constraints in absolute terms)
system: DOCUMENT PASSAGES: [CIT-1]…[CIT-N]   (the bounded retrieval context)
user/assistant: <last 8 messages of history> (conversation context, oldest first)
user: <current message>
```

The model is instructed: every factual claim must include an inline `[CIT-N]` marker, and unresolved citations are removed in post-processing.

### 3. Streaming

`stream_response()` is an async generator that calls `gpt-4o` via OpenRouter with `stream=True, temperature=0.1, max_tokens=600` and yields token deltas. The route wraps these in a `StreamingResponse` with SSE framing:

```
event: token        data: {"delta": "..."}
event: citations    data: [{cit_id, document_id, section, snippet}, ...]
event: done         data: {"message_id": "..."}
event: error        data: {"detail": "..."}
```

### 4. Persistence

Once the stream completes, both messages are persisted in `messages` (user message first via direct insert before streaming, assistant message after with parsed citations). On the first exchange, the conversation auto-titles itself with the truncated first user message.

---

## Database Schema

Migration `a8b9c0d1e2f3_chat_tables.py`:

### `conversations`

```sql
id UUID PK
user_id UUID -> users(id) ON DELETE CASCADE NOT NULL
scope_type TEXT NOT NULL                            -- 'document' | 'result_set'
scope_document_id UUID -> documents(id) ON DELETE CASCADE NULL
scope_query TEXT NULL                               -- reserved for result_set scope (V1.1)
scope_filters JSONB NULL                            -- reserved for result_set scope
title TEXT NULL                                     -- auto-generated from first user message
created_at, updated_at
```

Indexes: `(user_id, updated_at DESC)` for the list page, `(scope_document_id)` for joins.

### `messages`

```sql
id UUID PK
conversation_id UUID -> conversations(id) ON DELETE CASCADE NOT NULL
role TEXT NOT NULL                                  -- 'user' | 'assistant'
content TEXT NOT NULL
citations JSONB NULL                                -- [{cit_id, document_id, section, snippet}, ...]
created_at
```

Index: `(conversation_id, created_at)` for ordered fetch.

---

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/chat/conversations` | Create — body = `{scope_type, scope_document_id}`. `result_set` returns 501 (deferred to V1.1). |
| `GET` | `/api/chat/conversations` | List user's conversations, paginated, sorted by `updated_at DESC`. Joins `documents` + `document_metadata` so each row carries `scope_doc_type`, `scope_doc_facility_name`, `scope_doc_jurisdiction`, and a correlated-subquery `message_count`. |
| `GET` | `/api/chat/conversations/{id}` | Get a conversation with the full ordered message history. 403 if the caller isn't the owner. |
| `POST` | `/api/chat/conversations/{id}/messages` | Send a user message; returns an SSE stream. |

All endpoints require auth (`Depends(get_current_user)`).

---

## Frontend Components

### `src/lib/api.ts`

| Function | What |
|---|---|
| `createConversation({scope_type, scope_document_id})` | POST create, returns the empty conversation. |
| `getConversation(id)` | GET full thread. |
| `listConversations(page, page_size)` | GET paginated list with joined doc context. |
| `streamMessage(convId, content, onEvent, signal)` | POST + SSE reader using `fetch` + `ReadableStream` (since `EventSource` doesn't support custom Authorization headers). Parses `event:` / `data:` framing, dispatches typed `ChatStreamEvent` callbacks. Supports `AbortController` cancellation. |

### `src/components/chat/`

| Component | Purpose |
|---|---|
| `citation-pill.tsx` | Inline `[CIT-N]` marker. Hover/focus reveals a 320px snippet preview popover. |
| `message.tsx` | Renders user (right-aligned bubble) and assistant (left-aligned with eyebrow + blinking caret while streaming) messages. Parses `[CIT-N]` markers in assistant content and inlines `CitationPill` components. |
| `chat-panel.tsx` | 480px slide-in panel for `/documents/[id]`. Auto-creates a document-scoped conversation on mount. Shows the constraint notice + 4 suggested prompts on empty state. |

### Pages

| Route | What |
|---|---|
| `/documents/[id]` | "Ask about this document" button in the breadcrumb opens the slide-in `ChatPanel` as a third pane alongside metadata + PDF. |
| `/chat` | List of all past conversations. Each card shows doc-type tag, message count, title, `About: <facility name> · <jurisdiction>`, and a relative timestamp. Empty state deep-links to Search/Documents. |
| `/chat/[id]` | Full conversation thread view. Header shows doc-type tag, title, `About: <facility>` with a "View document →" link to the source. Reuses `ChatMessage` for rendering and the same streaming pipeline for continuing the conversation. |

---

## SSE on the Frontend

`EventSource` can't be used because it doesn't support custom `Authorization` headers, and we need JWT-based auth. Instead, `streamMessage()` does a regular `fetch` POST and reads the response body as a `ReadableStream`, decoding chunks into UTF-8 and splitting on the SSE separator (`\n\n`). Each event is parsed with a small `parseSseEvent()` helper that handles the `event: <name>` and `data: <json>` lines.

Cancellation is supported via `AbortSignal` — the chat panel calls `abort()` on unmount to terminate in-flight streams cleanly.

---

## Session Change

`expire_on_commit=False` was added to `AsyncSessionLocal` in `app/db/session.py`. Without this, every `await db.commit()` expires all ORM attributes on currently-attached objects, and any subsequent attribute access triggers a synchronous re-fetch — which `MissingGreenlet`s in async context. With it off, captured ORM objects remain usable across the commit boundary without explicit refresh, which is the standard pattern for async SQLAlchemy.

---

## What's Deferred (V1.1)

| Item | Why deferred |
|---|---|
| **Result-set scope chat** ("ask across these N search results") | Complex: re-run hybrid retrieval per turn with the saved query + filters, decide top-K passages across multiple documents, manage token budget. The `conversations` schema already has `scope_query` + `scope_filters` fields for this — the route currently returns 501 for `scope_type=result_set`. |
| **Real per-passage page numbers** | Would require building a char-offset → PDF-page mapping during ingestion. Current fallback (section header or `Passage N`) is workable for V1. |
| **Conversation delete / rename** | Backend cascade is in place via `ON DELETE CASCADE`; UI controls not yet built. |
| **In-page citation jumping** | Clicking a citation pill could jump the PDF viewer to the cited page. Requires real page numbers first. |

---

## How to Test

### Backend (curl-equivalent via PowerShell)

```powershell
# Login
$login = Invoke-RestMethod -Uri 'http://localhost:8000/api/auth/login' `
  -Method Post -ContentType 'application/json' `
  -Body '{"email":"test@example.com","password":"test1234"}'
$headers = @{ Authorization = "Bearer $($login.access_token)"; 'Content-Type' = 'application/json' }

# Create a conversation scoped to a document
$conv = Invoke-RestMethod -Uri 'http://localhost:8000/api/chat/conversations' `
  -Method Post -Headers $headers `
  -Body '{"scope_type":"document","scope_document_id":"<doc-uuid>"}'

# Stream a message (use a raw HttpWebRequest for SSE — Invoke-RestMethod can't stream)
# See chat smoke-test in Phase 6 commit for the full pattern.
```

### Frontend

1. Log in at `/login`.
2. Open any document via Search or Documents.
3. Click "Ask about this document" in the breadcrumb.
4. Ask "What did the inspector document?" — watch the response stream in with `[CIT-N]` pills you can hover.
5. Visit `/chat` to see the conversation in the history list.
6. Click in — read or continue.

---

## Cost & Latency

| Component | Latency | Cost per message |
|---|---|---|
| Passage prep | <100ms | $0 |
| `gpt-4o` streaming (avg 400-token response) | 3–6s end to end (first token at ~1s) | ~$0.01 |
| Citation parsing | <10ms | $0 |
| Persistence | <50ms | $0 |

`gpt-4o` is the chat model per CLAUDE.md (`llm_chat_model` in Settings — `openai/gpt-4o` via OpenRouter). A typical 10-turn conversation costs roughly $0.10–$0.20. The model can be swapped via env var.
