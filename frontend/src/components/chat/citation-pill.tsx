"use client";

import { useState } from "react";

import type { Citation } from "@/lib/api";

/**
 * Inline citation marker. Hover or focus to reveal a snippet preview.
 * Used to render [CIT-N] markers from the assistant's response.
 */
export function CitationPill({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="inline-flex items-center mx-0.5 px-1 py-px font-mono text-[10px] uppercase tracking-wider rounded-sm border border-accent/40 bg-accent-muted text-accent hover:border-accent hover:bg-accent/20 transition-colors align-baseline"
        aria-label={`Citation ${citation.cit_id}: ${citation.section ?? "passage"}`}
      >
        {citation.cit_id}
      </button>
      {open && (
        <span className="absolute left-1/2 z-50 -translate-x-1/2 translate-y-1 mt-1 w-80 rounded-sm border border-border-strong bg-surface-3 shadow-2 p-3 text-xs text-secondary leading-[1.5] pointer-events-none">
          <span className="block font-mono text-[10px] uppercase tracking-wider text-accent mb-1.5">
            [CIT-{citation.cit_id}] · {citation.section ?? "passage"}
          </span>
          <span className="block">{citation.snippet}</span>
        </span>
      )}
    </span>
  );
}
