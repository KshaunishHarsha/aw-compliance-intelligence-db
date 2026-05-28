"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  ApiError,
  listConversations,
  type ConversationListItem,
} from "@/lib/api";

const DOC_TYPE_LABEL: Record<string, string> = {
  inspection_report: "Inspection Report",
  regulation: "Regulation",
  policy: "Policy",
  enforcement_action: "Enforcement Action",
};

function formatRelative(iso: string): string {
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function ConversationRow({ conv }: { conv: ConversationListItem }) {
  const docLabel = conv.scope_doc_type
    ? (DOC_TYPE_LABEL[conv.scope_doc_type] ?? conv.scope_doc_type)
    : "—";
  const docTitle =
    conv.scope_doc_facility_name ??
    conv.scope_doc_original_name?.replace(/\.pdf$/i, "") ??
    "—";
  const title = conv.title?.trim() || "(no title yet)";

  return (
    <Link
      href={`/chat/${conv.id}`}
      className="block surface-2 border border-border-subtle rounded-sm px-5 py-4 hover:border-accent/60 transition-colors group"
    >
      <div className="flex items-start justify-between gap-6">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex items-center rounded-sm border border-accent/30 bg-accent-muted px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-accent">
              {docLabel}
            </span>
            <span className="font-mono text-[10px] text-tertiary">
              {conv.message_count} {conv.message_count === 1 ? "message" : "messages"}
            </span>
          </div>
          <h3 className="text-base text-primary font-medium leading-[1.35] group-hover:text-accent transition-colors break-words">
            {title}
          </h3>
          <div className="mt-1.5 flex items-center gap-2 font-mono text-[11px] text-tertiary">
            <span>About:</span>
            <span className="text-secondary truncate">{docTitle}</span>
            {conv.scope_doc_jurisdiction && (
              <>
                <span>·</span>
                <span>{conv.scope_doc_jurisdiction}</span>
              </>
            )}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
            Last activity
          </div>
          <div className="font-mono text-xs text-secondary mt-0.5">
            {formatRelative(conv.updated_at)}
          </div>
        </div>
      </div>
    </Link>
  );
}

export default function ChatListPage() {
  const [items, setItems] = useState<ConversationListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listConversations(1, 50)
      .then((r) => {
        if (cancelled) return;
        setItems(r.items);
        setTotal(r.total);
      })
      .catch((err) => {
        if (cancelled) return;
        const msg =
          err instanceof ApiError
            ? `${err.status}: ${err.message}`
            : err instanceof Error
              ? err.message
              : "Failed to load";
        setError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="border-b border-border-subtle bg-surface-1 px-8 py-6">
        <div className="max-w-3xl">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-accent">
            Grounded Chat · History
          </div>
          <h1 className="mt-1 font-display text-3xl font-medium text-primary">
            Conversations
          </h1>
          <p className="mt-2 text-sm text-secondary max-w-2xl">
            Every chat thread you&apos;ve opened across the corpus. Click into
            any to read the history or continue the conversation. To start a
            new chat, open a document and click <em>Ask about this document</em>.
          </p>
        </div>
      </div>

      <div className="px-8 py-6">
        <div className="max-w-3xl space-y-3">
          {loading && (
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-tertiary">
              Loading conversations…
            </div>
          )}

          {error && (
            <div className="border border-critical/40 bg-critical-muted rounded-sm p-4">
              <div className="font-mono text-[10px] uppercase tracking-wider text-critical mb-1">
                Failed to load
              </div>
              <p className="text-sm text-secondary">{error}</p>
            </div>
          )}

          {!loading && !error && items.length === 0 && (
            <div className="border border-border-subtle bg-surface-2 rounded-sm p-8 text-center">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-tertiary mb-2">
                No conversations yet
              </div>
              <p className="text-sm text-secondary max-w-md mx-auto">
                Open any document in{" "}
                <Link href="/search" className="text-accent hover:underline">
                  Search
                </Link>{" "}
                or{" "}
                <Link href="/documents" className="text-accent hover:underline">
                  Documents
                </Link>{" "}
                and click <em>Ask about this document</em> to start one.
              </p>
            </div>
          )}

          {items.map((c) => (
            <ConversationRow key={c.id} conv={c} />
          ))}

          {!loading && total > items.length && (
            <div className="font-mono text-[11px] text-tertiary text-center pt-2">
              Showing {items.length} of {total}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
