"use client";

import Link from "next/link";

import type { SearchResult } from "@/lib/api";

const DOC_TYPE_LABEL: Record<string, string> = {
  inspection_report: "Inspection Report",
  regulation: "Regulation",
  policy: "Policy",
  enforcement_action: "Enforcement Action",
};

function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
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

function CategoryTag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-sm border border-border-default bg-surface-3 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-secondary">
      {children}
    </span>
  );
}

export function ResultCard({
  result,
  rank,
}: {
  result: SearchResult;
  rank: number;
}) {
  const m = result.metadata;
  const docTypeLabel =
    result.doc_type && DOC_TYPE_LABEL[result.doc_type]
      ? DOC_TYPE_LABEL[result.doc_type]
      : result.doc_type;
  const facilityOrTitle =
    m?.facility_name ?? result.original_name.replace(/\.pdf$/i, "");
  const inspectionDate = formatDate(m?.inspection_date);

  return (
    <Link
      href={`/documents/${result.id}`}
      className="block surface-2 border border-border-subtle rounded-sm hover:border-accent/60 transition-colors group"
    >
    <article>
      <div className="border-b border-border-subtle px-6 py-5">
        <div className="flex items-start justify-between gap-6">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2.5 mb-2.5">
              <span className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
                #{String(rank).padStart(2, "0")}
              </span>
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
            <h3 className="font-display text-xl font-medium text-primary leading-[1.25] break-words group-hover:text-accent transition-colors">
              {facilityOrTitle}
            </h3>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-tertiary">
              {m?.jurisdiction && <span>{m.jurisdiction}</span>}
              {m?.jurisdiction && inspectionDate && <span>·</span>}
              {inspectionDate && <span>{inspectionDate}</span>}
              {m?.inspector_name && (
                <>
                  <span>·</span>
                  <span>{m.inspector_name}</span>
                </>
              )}
            </div>
          </div>
          <div className="text-right shrink-0">
            <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
              Match
            </div>
            <div className="font-display text-3xl font-medium text-accent leading-none mt-0.5">
              {result.scores.final_score.toFixed(2)}
            </div>
            <div className="font-mono text-[10px] text-tertiary mt-1">
              v {result.scores.vector_score.toFixed(2)} · bm{" "}
              {result.scores.bm25_score.toFixed(2)}
              {result.scores.metadata_boost > 0 && (
                <> · meta {result.scores.metadata_boost.toFixed(2)}</>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="px-6 py-5 space-y-4">
        {result.retrieval_summary && (
          <p className="text-base text-secondary leading-[1.55]">
            {result.retrieval_summary}
          </p>
        )}

        {result.match_reason && (
          <div className="border-l-2 border-accent pl-4 py-1 bg-accent-muted/30">
            <div className="font-mono text-[10px] uppercase tracking-wider text-accent mb-1">
              Why this matched
            </div>
            <p className="text-sm text-secondary leading-[1.55]">
              {result.match_reason}
            </p>
          </div>
        )}

        {(m?.categories?.length || m?.species?.length) && (
          <div className="flex flex-wrap items-center gap-3 pt-1">
            {m?.categories && m.categories.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
                  Categories
                </span>
                {m.categories.map((c) => (
                  <CategoryTag key={c}>{c.replace(/_/g, " ")}</CategoryTag>
                ))}
              </div>
            )}
            {m?.species && m.species.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
                  Species
                </span>
                {m.species.slice(0, 6).map((s) => (
                  <CategoryTag key={s}>{s}</CategoryTag>
                ))}
                {m.species.length > 6 && (
                  <span className="font-mono text-[10px] text-tertiary">
                    +{m.species.length - 6}
                  </span>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </article>
    </Link>
  );
}
