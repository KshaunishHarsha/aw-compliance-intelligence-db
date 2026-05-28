"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";

import { ChatMessage } from "@/components/chat/message";
import {
  ApiError,
  getConversation,
  getDocument,
  streamMessage,
  type ChatMessage as ChatMessageT,
  type Citation,
  type Conversation,
  type DocumentResponse,
} from "@/lib/api";

const DOC_TYPE_LABEL: Record<string, string> = {
  inspection_report: "Inspection Report",
  regulation: "Regulation",
  policy: "Policy",
  enforcement_action: "Enforcement Action",
};

interface UiMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  streaming?: boolean;
}

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function ChatThreadPage({ params }: PageProps) {
  const { id } = use(params);

  const [conv, setConv] = useState<Conversation | null>(null);
  const [scopeDoc, setScopeDoc] = useState<DocumentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    getConversation(id)
      .then(async (c) => {
        if (cancelled) return;
        setConv(c);
        setMessages(
          c.messages.map((m: ChatMessageT) => ({
            id: m.id,
            role: m.role as "user" | "assistant",
            content: m.content,
            citations: m.citations,
          })),
        );
        if (c.scope_document_id) {
          try {
            const d = await getDocument(c.scope_document_id);
            if (!cancelled) setScopeDoc(d);
          } catch {
            // Source doc may have been deleted; header falls back.
          }
        }
      })
      .catch((err) => {
        if (cancelled) return;
        const msg =
          err instanceof ApiError
            ? err.status === 404
              ? "Conversation not found."
              : `${err.status}: ${err.message}`
            : err instanceof Error
              ? err.message
              : "Failed to load conversation";
        setLoadError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [id]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || !conv || sending) return;

    setSendError(null);
    setInput("");

    const userMsg: UiMessage = {
      id: `local-${Date.now()}-u`,
      role: "user",
      content: text,
      citations: null,
    };
    const assistantId = `local-${Date.now()}-a`;
    const assistantMsg: UiMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      citations: null,
      streaming: true,
    };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setSending(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      await streamMessage(
        conv.id,
        text,
        (e) => {
          if (e.event === "token") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: m.content + e.data.delta }
                  : m,
              ),
            );
          } else if (e.event === "citations") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, citations: e.data } : m,
              ),
            );
          } else if (e.event === "done") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, id: e.data.message_id, streaming: false }
                  : m,
              ),
            );
          } else if (e.event === "error") {
            setSendError(e.data.detail);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, streaming: false } : m,
              ),
            );
          }
        },
        ctrl.signal,
      );
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      const msg =
        err instanceof ApiError
          ? `${err.status}: ${err.message}`
          : err instanceof Error
            ? err.message
            : "Send failed";
      setSendError(msg);
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m)),
      );
    } finally {
      setSending(false);
    }
  }, [input, conv, sending]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-tertiary">
          Loading conversation…
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="px-8 py-12 max-w-2xl">
        <Link
          href="/chat"
          className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary hover:text-accent transition-colors"
        >
          ← All conversations
        </Link>
        <div className="mt-6 border border-critical/40 bg-critical-muted rounded-sm p-6">
          <div className="font-mono text-[10px] uppercase tracking-wider text-critical mb-2">
            Could not open conversation
          </div>
          <p className="text-sm text-secondary">{loadError}</p>
        </div>
      </div>
    );
  }

  if (!conv) return null;

  const docTypeLabel = scopeDoc?.doc_type
    ? (DOC_TYPE_LABEL[scopeDoc.doc_type] ?? scopeDoc.doc_type)
    : null;
  const facilityName =
    scopeDoc?.metadata?.facility_name ??
    scopeDoc?.original_name?.replace(/\.pdf$/i, "") ??
    null;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border-subtle bg-surface-1 px-8 py-4">
        <div className="max-w-3xl">
          <Link
            href="/chat"
            className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary hover:text-accent transition-colors"
          >
            ← All conversations
          </Link>
          <div className="mt-2">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-accent mb-1">
              {docTypeLabel ?? "Conversation"}
            </div>
            <h1 className="font-display text-2xl font-medium text-primary leading-[1.25] break-words">
              {conv.title ?? "(no title)"}
            </h1>
            {conv.scope_document_id && (
              <div className="mt-1.5 flex items-center gap-2 font-mono text-[11px] text-tertiary">
                <span>About:</span>
                {facilityName && (
                  <span className="text-secondary">{facilityName}</span>
                )}
                <Link
                  href={`/documents/${conv.scope_document_id}`}
                  className="text-accent hover:underline"
                >
                  View document →
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Constraint notice */}
      <div className="border-b border-border-subtle bg-surface-2 px-8 py-2.5">
        <p className="max-w-3xl text-[11px] text-tertiary leading-[1.5]">
          Answers cite passages from the source document only. The assistant
          does not draw legal conclusions or call findings violations.
        </p>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-8 py-8">
        <div className="max-w-3xl space-y-6">
          {messages.length === 0 && (
            <div className="font-mono text-[11px] text-tertiary">
              No messages yet. Start the conversation below.
            </div>
          )}
          {messages.map((m) => (
            <ChatMessage
              key={m.id}
              role={m.role}
              content={m.content}
              citations={m.citations}
              streaming={m.streaming}
            />
          ))}
          {sendError && (
            <div className="border border-critical/40 bg-critical-muted rounded-sm p-3">
              <div className="font-mono text-[10px] uppercase tracking-wider text-critical mb-1">
                Stream error
              </div>
              <p className="text-xs text-secondary">{sendError}</p>
            </div>
          )}
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-border-subtle bg-surface-1 px-8 py-4">
        <div className="max-w-3xl">
          <div className="relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Continue the conversation — Enter to send, Shift+Enter for newline"
              rows={2}
              disabled={sending}
              className="block w-full rounded-sm border border-border-default bg-surface-2 px-3 py-2 pr-20 text-sm text-primary placeholder:text-tertiary focus:border-accent focus:outline-none resize-none disabled:opacity-50"
            />
            <button
              type="button"
              onClick={send}
              disabled={!input.trim() || sending}
              className="absolute right-2 bottom-2 rounded-sm bg-accent px-3 py-1 text-xs font-medium text-accent-foreground hover:bg-accent-hover disabled:cursor-not-allowed disabled:bg-surface-3 disabled:text-disabled"
            >
              {sending ? "…" : "Send"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
