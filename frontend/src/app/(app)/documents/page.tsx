"use client";

// Force dynamic rendering — page depends on URL params + client-side auth.
export const dynamic = "force-dynamic";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  listDocuments,
  type DocType,
  type DocumentListResponse,
  type DocumentResponse,
  type Source,
} from "@/lib/api";

const DOC_TYPES: { value: DocType; label: string }[] = [
  { value: "inspection_report", label: "Inspection Reports" },
  { value: "regulation", label: "Regulations" },
  { value: "policy", label: "Policy" },
  { value: "enforcement_action", label: "Enforcement" },
];

const SOURCES: { value: Source; label: string }[] = [
  { value: "USDA_APHIS", label: "USDA APHIS" },
  { value: "CFR_Title9", label: "9 CFR Title 9" },
  { value: "APHIS_Enforcement", label: "APHIS Enforcement" },
];

const DOC_TYPE_LABEL: Record<string, string> = {
  inspection_report: "Inspection Report",
  regulation: "Regulation",
  policy: "Policy",
  enforcement_action: "Enforcement Action",
};

const PAGE_SIZE = 25;

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function ChipButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-sm border px-2.5 py-1 text-left font-mono text-[11px] uppercase tracking-wider transition-colors ${
        active
          ? "bg-accent-muted text-accent border-accent/40"
          : "border-border-default text-secondary hover:border-border-strong hover:text-primary"
      }`}
    >
      {label}
    </button>
  );
}

function DocumentRow({ document }: { document: DocumentResponse }) {
  const m = document.metadata;
  const title = m?.facility_name ?? document.original_name.replace(/\.pdf$/i, "");
  const docTypeLabel = document.doc_type
    ? (DOC_TYPE_LABEL[document.doc_type] ?? document.doc_type)
    : "—";
  return (
    <Link
      href={`/documents/${document.id}`}
      className="grid grid-cols-12 items-center gap-3 px-4 py-3 border-b border-border-subtle hover:bg-surface-2 transition-colors group"
    >
      <div className="col-span-2 font-mono text-[10px] uppercase tracking-wider text-tertiary">
        {docTypeLabel}
      </div>
      <div className="col-span-5 min-w-0">
        <div className="text-sm text-primary truncate group-hover:text-accent transition-colors">
          {title}
        </div>
        <div className="font-mono text-[10px] text-tertiary truncate">
          {document.original_name}
        </div>
      </div>
      <div className="col-span-1 font-mono text-xs text-secondary">
        {m?.jurisdiction ?? "—"}
      </div>
      <div className="col-span-2 font-mono text-xs text-secondary">
        {formatDate(m?.inspection_date)}
      </div>
      <div className="col-span-2 font-mono text-[10px] text-tertiary text-right">
        {m?.reference_number ?? ""}
      </div>
    </Link>
  );
}

export default function DocumentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const docType =
    (searchParams.get("doc_type") as DocType | null) || undefined;
  const source = (searchParams.get("source") as Source | null) || undefined;
  const page = Number(searchParams.get("page") || "1");

  const [data, setData] = useState<DocumentListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateParams = useCallback(
    (next: { doc_type?: DocType; source?: Source; page?: number }) => {
      const qs = new URLSearchParams();
      const finalDocType = next.doc_type !== undefined ? next.doc_type : docType;
      const finalSource = next.source !== undefined ? next.source : source;
      const finalPage = next.page ?? 1;
      if (finalDocType) qs.set("doc_type", finalDocType);
      if (finalSource) qs.set("source", finalSource);
      if (finalPage > 1) qs.set("page", String(finalPage));
      const suffix = qs.toString() ? `?${qs.toString()}` : "";
      router.replace(`/documents${suffix}`);
    },
    [router, docType, source],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listDocuments({
      page,
      page_size: PAGE_SIZE,
      doc_type: docType,
      source,
    })
      .then((d) => {
        if (!cancelled) setData(d);
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
  }, [page, docType, source]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="flex h-full">
      {/* Left filter rail */}
      <aside className="w-64 shrink-0 border-r border-border-subtle bg-surface-1 overflow-y-auto">
        <div className="px-6 py-5 border-b border-border-subtle">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary">
            Browse
          </div>
          <div className="font-display text-lg font-medium text-primary mt-0.5">
            Corpus
          </div>
        </div>

        <div className="px-6 py-5 space-y-6">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary mb-3">
              Document Type
            </div>
            <div className="flex flex-col gap-1.5">
              {DOC_TYPES.map((dt) => (
                <ChipButton
                  key={dt.value}
                  label={dt.label}
                  active={docType === dt.value}
                  onClick={() =>
                    updateParams({
                      doc_type: docType === dt.value ? undefined : dt.value,
                      page: 1,
                    })
                  }
                />
              ))}
            </div>
          </div>

          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary mb-3">
              Source
            </div>
            <div className="flex flex-col gap-1.5">
              {SOURCES.map((s) => (
                <ChipButton
                  key={s.value}
                  label={s.label}
                  active={source === s.value}
                  onClick={() =>
                    updateParams({
                      source: source === s.value ? undefined : s.value,
                      page: 1,
                    })
                  }
                />
              ))}
            </div>
          </div>

          {(docType || source) && (
            <button
              type="button"
              onClick={() => updateParams({ doc_type: undefined, source: undefined, page: 1 })}
              className="text-xs text-tertiary hover:text-accent transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="border-b border-border-subtle bg-surface-1 px-6 py-5">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-accent">
            Corpus Browser
          </div>
          <h1 className="mt-1 font-display text-3xl font-medium text-primary">
            Documents
          </h1>
          <p className="mt-2 text-sm text-secondary max-w-2xl">
            Every leaf document in the corpus. For relevance-ranked search with
            free-text query, use the{" "}
            <Link href="/search" className="text-accent hover:underline">
              Search
            </Link>{" "}
            page.
          </p>
        </div>

        {/* Counts + pagination header */}
        <div className="flex items-center justify-between border-b border-border-subtle px-6 py-3">
          <div className="font-mono text-xs text-tertiary">
            {loading && !data ? (
              "Loading…"
            ) : data ? (
              <>
                <span className="text-secondary">{data.total.toLocaleString()}</span>{" "}
                documents · page{" "}
                <span className="text-secondary">{data.page}</span> of{" "}
                <span className="text-secondary">{totalPages}</span>
              </>
            ) : (
              "—"
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => updateParams({ page: Math.max(1, page - 1) })}
              disabled={page <= 1 || loading}
              className="rounded-sm border border-border-default bg-surface-2 px-2.5 py-1 font-mono text-xs text-secondary hover:border-border-strong hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
            >
              ← Prev
            </button>
            <button
              type="button"
              onClick={() => updateParams({ page: Math.min(totalPages, page + 1) })}
              disabled={page >= totalPages || loading}
              className="rounded-sm border border-border-default bg-surface-2 px-2.5 py-1 font-mono text-xs text-secondary hover:border-border-strong hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        </div>

        {/* Table */}
        {error ? (
          <div className="px-6 py-8">
            <div className="max-w-2xl border border-critical/40 bg-critical-muted rounded-sm p-6">
              <div className="font-mono text-[10px] uppercase tracking-wider text-critical mb-2">
                Failed to load
              </div>
              <p className="text-sm text-secondary">{error}</p>
            </div>
          </div>
        ) : (
          <>
            {/* Column header */}
            <div className="grid grid-cols-12 gap-3 px-4 py-2 border-b border-border-default bg-surface-2 font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary">
              <div className="col-span-2">Type</div>
              <div className="col-span-5">Document</div>
              <div className="col-span-1">Juris.</div>
              <div className="col-span-2">Date</div>
              <div className="col-span-2 text-right">Reference</div>
            </div>

            {loading && !data
              ? Array.from({ length: 8 }).map((_, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-12 gap-3 px-4 py-3 border-b border-border-subtle animate-pulse"
                    style={{ opacity: 1 - i * 0.08 }}
                  >
                    <div className="col-span-2 h-3 bg-surface-3 rounded-sm" />
                    <div className="col-span-5 h-3 bg-surface-3 rounded-sm" />
                    <div className="col-span-1 h-3 bg-surface-3 rounded-sm" />
                    <div className="col-span-2 h-3 bg-surface-3 rounded-sm" />
                    <div className="col-span-2 h-3 bg-surface-3 rounded-sm" />
                  </div>
                ))
              : data?.items.map((d) => <DocumentRow key={d.id} document={d} />)}

            {data && data.items.length === 0 && (
              <div className="px-6 py-16 text-center">
                <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-tertiary mb-2">
                  No documents
                </div>
                <p className="text-sm text-secondary">
                  Nothing matches the current filter selection.
                </p>
              </div>
            )}
          </>
        )}

        {/* Bottom pagination */}
        {data && data.items.length > 0 && totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-border-subtle px-6 py-4">
            <div className="font-mono text-xs text-tertiary">
              Page {data.page} of {totalPages}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => updateParams({ page: Math.max(1, page - 1) })}
                disabled={page <= 1 || loading}
                className="rounded-sm border border-border-default bg-surface-2 px-2.5 py-1 font-mono text-xs text-secondary hover:border-border-strong hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
              >
                ← Prev
              </button>
              <button
                type="button"
                onClick={() => updateParams({ page: Math.min(totalPages, page + 1) })}
                disabled={page >= totalPages || loading}
                className="rounded-sm border border-border-default bg-surface-2 px-2.5 py-1 font-mono text-xs text-secondary hover:border-border-strong hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
