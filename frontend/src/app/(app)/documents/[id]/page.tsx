"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { use, useEffect, useState } from "react";

import { ChatPanel } from "@/components/chat/chat-panel";
import { MetadataPanel } from "@/components/document/metadata-panel";
import {
  ApiError,
  getDocument,
  getDocumentUrl,
  type DocumentResponse,
} from "@/lib/api";

// PDFViewer pulls in pdf.js which is browser-only — skip SSR to avoid the
// "legacy build in Node.js environments" warning and a wasted server render.
const PDFViewer = dynamic(
  () => import("@/components/document/pdf-viewer").then((m) => m.PDFViewer),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center bg-surface-1 font-mono text-[10px] uppercase tracking-[0.2em] text-tertiary">
        Loading PDF viewer…
      </div>
    ),
  },
);

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function DocumentDetailPage({ params }: PageProps) {
  const { id } = use(params);

  const [doc, setDoc] = useState<DocumentResponse | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [chatOpen, setChatOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([getDocument(id), getDocumentUrl(id)])
      .then(([d, u]) => {
        if (cancelled) return;
        setDoc(d);
        setUrl(u.url);
      })
      .catch((err) => {
        if (cancelled) return;
        const msg =
          err instanceof ApiError
            ? err.status === 404
              ? "Document not found."
              : `${err.status}: ${err.message}`
            : err instanceof Error
              ? err.message
              : "Failed to load document";
        setError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  // ── Loading ───────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-tertiary">
          Loading document…
        </div>
      </div>
    );
  }

  // ── Error ─────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="px-8 py-12 max-w-2xl">
        <Link
          href="/search"
          className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary hover:text-accent transition-colors"
        >
          ← Back to search
        </Link>
        <div className="mt-6 border border-critical/40 bg-critical-muted rounded-sm p-6">
          <div className="font-mono text-[10px] uppercase tracking-wider text-critical mb-2">
            Could not open document
          </div>
          <p className="text-sm text-secondary">{error}</p>
        </div>
      </div>
    );
  }

  if (!doc || !url) return null;

  return (
    <div className="flex h-full flex-col">
      {/* Breadcrumb bar */}
      <div className="flex items-center gap-4 border-b border-border-subtle bg-surface-1 px-6 py-2.5">
        <Link
          href="/search"
          className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary hover:text-accent transition-colors"
        >
          ← Back to search
        </Link>
        <span className="font-mono text-[11px] text-tertiary">/</span>
        <span className="font-mono text-[11px] text-secondary truncate flex-1">
          {doc.metadata?.facility_name ??
            doc.original_name.replace(/\.pdf$/i, "")}
        </span>
        {!chatOpen && (
          <button
            type="button"
            onClick={() => setChatOpen(true)}
            className="rounded-sm border border-accent/40 bg-accent-muted px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider text-accent hover:border-accent hover:bg-accent/20 transition-colors"
          >
            Ask about this document
          </button>
        )}
      </div>

      {/* Multi-pane layout */}
      <div className="flex flex-1 overflow-hidden">
        <MetadataPanel document={doc} />
        <div className="flex-1 overflow-hidden">
          <PDFViewer
            url={url}
            initialPage={doc.page_start ?? null}
            pageEnd={doc.page_end ?? null}
          />
        </div>
        {chatOpen && (
          <ChatPanel
            documentId={doc.id}
            documentTitle={
              doc.metadata?.facility_name ??
              doc.original_name.replace(/\.pdf$/i, "")
            }
            onClose={() => setChatOpen(false)}
          />
        )}
      </div>
    </div>
  );
}
