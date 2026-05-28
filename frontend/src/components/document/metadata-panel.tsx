"use client";

import type { DocumentResponse } from "@/lib/api";

const DOC_TYPE_LABEL: Record<string, string> = {
  inspection_report: "Inspection Report",
  regulation: "Regulation",
  policy: "Policy",
  enforcement_action: "Enforcement Action",
};

function formatDate(iso?: string | null): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function MetaRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline gap-3 border-b border-border-subtle py-2.5 last:border-b-0">
      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary min-w-[110px]">
        {label}
      </span>
      <span
        className={`text-sm text-primary break-words ${mono ? "font-mono" : ""}`}
      >
        {value}
      </span>
    </div>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-sm border border-border-default bg-surface-3 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-secondary">
      {children}
    </span>
  );
}

export function MetadataPanel({ document }: { document: DocumentResponse }) {
  const m = document.metadata;
  const docTypeLabel =
    document.doc_type && DOC_TYPE_LABEL[document.doc_type]
      ? DOC_TYPE_LABEL[document.doc_type]
      : document.doc_type;
  const inspectionDate = formatDate(m?.inspection_date);
  const title =
    m?.facility_name ?? document.original_name.replace(/\.pdf$/i, "");

  return (
    <aside className="flex w-[420px] shrink-0 flex-col border-r border-border-subtle bg-surface-1 overflow-y-auto">
      {/* Header */}
      <div className="px-6 py-5 border-b border-border-subtle">
        <div className="flex items-center gap-2 mb-3">
          {docTypeLabel && (
            <span className="inline-flex items-center rounded-sm border border-accent/30 bg-accent-muted px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-accent">
              {docTypeLabel}
            </span>
          )}
          {m?.reference_number && (
            <span className="font-mono text-xs text-tertiary">
              {m.reference_number}
            </span>
          )}
        </div>
        <h1 className="font-display text-2xl font-medium text-primary leading-[1.2] break-words">
          {title}
        </h1>
        <div className="mt-1.5 font-mono text-[11px] text-tertiary break-all">
          {document.original_name}
        </div>
      </div>

      {/* Retrieval summary */}
      {document.retrieval_summary && (
        <div className="px-6 py-5 border-b border-border-subtle">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary mb-3">
            Summary
          </div>
          <p className="text-sm text-secondary leading-[1.6]">
            {document.retrieval_summary}
          </p>
        </div>
      )}

      {/* Structured metadata */}
      <div className="px-6 py-5 border-b border-border-subtle">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary mb-3">
          Metadata
        </div>
        <div className="space-y-0">
          {m?.facility_name && <MetaRow label="Facility" value={m.facility_name} />}
          {m?.jurisdiction && <MetaRow label="Jurisdiction" value={m.jurisdiction} />}
          {inspectionDate && (
            <MetaRow label="Inspection Date" value={inspectionDate} />
          )}
          {m?.inspector_name && (
            <MetaRow label="Inspector" value={m.inspector_name} />
          )}
          {m?.reference_number && (
            <MetaRow label="Reference" value={m.reference_number} mono />
          )}
          {m?.issuer && <MetaRow label="Issuer" value={m.issuer} />}
          {document.source && <MetaRow label="Source" value={document.source} />}
        </div>
      </div>

      {/* Categories */}
      {m?.categories && m.categories.length > 0 && (
        <div className="px-6 py-5 border-b border-border-subtle">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary mb-3">
            Violation Categories
          </div>
          <div className="flex flex-wrap gap-1.5">
            {m.categories.map((c) => (
              <Tag key={c}>{c.replace(/_/g, " ")}</Tag>
            ))}
          </div>
        </div>
      )}

      {/* Species */}
      {m?.species && m.species.length > 0 && (
        <div className="px-6 py-5 border-b border-border-subtle">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary mb-3">
            Species ({m.species.length})
          </div>
          <div className="flex flex-wrap gap-1.5">
            {m.species.map((s) => (
              <Tag key={s}>{s}</Tag>
            ))}
          </div>
        </div>
      )}

      {/* Provenance footer */}
      <div className="px-6 py-4 mt-auto border-t border-border-subtle">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary mb-2">
          Provenance
        </div>
        <div className="space-y-1 font-mono text-[11px] text-tertiary">
          <div>
            <span className="text-secondary">Document ID</span> ·{" "}
            <span className="break-all">{document.id}</span>
          </div>
          {document.parent_document_id && (
            <div>
              <span className="text-secondary">Parent</span> ·{" "}
              <span className="break-all">{document.parent_document_id}</span>
            </div>
          )}
          <div>
            <span className="text-secondary">Status</span> · {document.status}
          </div>
        </div>
      </div>
    </aside>
  );
}
