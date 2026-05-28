"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  createConversation,
  streamMessage,
  type ChatMessage as ChatMessageT,
  type Citation,
  type Conversation,
} from "@/lib/api";

import { ChatMessage } from "./message";

interface ChatPanelProps {
  /** Document this chat is scoped to. */
  documentId: string;
  /** Short label for the doc — used in the header. */
  documentTitle: string;
  /** Close the panel. */
  onClose: () => void;
}

const SUGGESTED_PROMPTS = [
  "Summarize the inspector's findings.",
  "What CFR sections are cited?",
  "What species are involved?",
  "What corrective actions were required?",
];

interface UiMessage {
  id: string;          // local id — server id once persisted
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  streaming?: boolean;
}

export function ChatPanel({ documentId, documentTitle, onClose }: ChatPanelProps) {
  const [conv, setConv] = useState<Conversation | null>(null);
  const [creating, setCreating] = useState(true);
  const [createError, setCreateError] = useState<string | null>(null);

  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Lazily create a conversation when the panel first opens
  useEffect(() => {
    let cancelled = false;
    createConversation({ scope_type: "document", scope_document_id: documentId })
      .then((c) => {
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
      })
      .catch((err) => {
        if (cancelled) return;
        const msg =
          err instanceof ApiError
            ? `${err.status}: ${err.message}`
            : err instanceof Error
              ? err.message
              : "Failed to start conversation";
        setCreateError(msg);
      })
      .finally(() => {
        if (!cancelled) setCreating(false);
      });
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [documentId]);

  // Auto-scroll to bottom on new content
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

  return (
    <div className="flex h-full w-[480px] shrink-0 flex-col border-l border-border-subtle bg-surface-1">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 border-b border-border-subtle px-5 py-4">
        <div className="min-w-0">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-accent">
            Grounded Chat
          </div>
          <div className="mt-0.5 font-display text-base font-medium text-primary truncate">
            {documentTitle}
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="font-mono text-[10px] uppercase tracking-wider text-tertiary hover:text-accent transition-colors"
          aria-label="Close chat"
        >
          Close ✕
        </button>
      </div>

      {/* Constraint notice */}
      <div className="border-b border-border-subtle px-5 py-2.5 bg-surface-2">
        <p className="text-[11px] text-tertiary leading-[1.5]">
          Answers cite passages from this document only. The assistant does not
          draw legal conclusions or call findings violations — it surfaces what
          the report says.
        </p>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
        {creating && (
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-tertiary">
            Starting conversation…
          </div>
        )}
        {createError && (
          <div className="border border-critical/40 bg-critical-muted rounded-sm p-3">
            <div className="font-mono text-[10px] uppercase tracking-wider text-critical mb-1">
              Could not start conversation
            </div>
            <p className="text-xs text-secondary">{createError}</p>
          </div>
        )}

        {!creating && messages.length === 0 && (
          <div>
            <p className="text-sm text-secondary leading-[1.55]">
              Ask anything about this document. The assistant cites its sources.
            </p>
            <div className="mt-4 flex flex-col gap-1.5">
              {SUGGESTED_PROMPTS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setInput(p)}
                  className="text-left text-sm text-tertiary hover:text-accent transition-colors px-2 py-1.5 rounded-sm border border-border-subtle hover:border-accent/40"
                >
                  {p}
                </button>
              ))}
            </div>
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

      {/* Input */}
      <div className="border-t border-border-subtle bg-surface-1 px-5 py-3">
        <div className="relative">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask about this document — Enter to send, Shift+Enter for newline"
            rows={2}
            disabled={creating || sending || !conv}
            className="block w-full rounded-sm border border-border-default bg-surface-2 px-3 py-2 pr-20 text-sm text-primary placeholder:text-tertiary focus:border-accent focus:outline-none resize-none disabled:opacity-50"
          />
          <button
            type="button"
            onClick={send}
            disabled={!input.trim() || sending || creating || !conv}
            className="absolute right-2 bottom-2 rounded-sm bg-accent px-3 py-1 text-xs font-medium text-accent-foreground hover:bg-accent-hover disabled:cursor-not-allowed disabled:bg-surface-3 disabled:text-disabled"
          >
            {sending ? "…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
