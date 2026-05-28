"use client";

import { useCallback, useMemo, useRef, useState } from "react";

import { ApiError, search } from "@/lib/api";
import type { SearchResponse } from "@/lib/api";
import { FilterSidebar, type FilterState } from "@/components/search/filter-sidebar";
import { ResultCard } from "@/components/search/result-card";
import { SearchInput } from "@/components/search/search-input";

const EXAMPLE_QUERIES = [
  "veterinary care violations for primates",
  "unsanitary enclosures for rabbits",
  "licensing requirements for dealers",
  "transport conditions for dogs",
];

function hasActiveFilters(f: FilterState): boolean {
  return Boolean(
    f.doc_type ||
      (f.categories && f.categories.length > 0) ||
      f.jurisdiction ||
      f.facility_name ||
      f.date_from ||
      f.date_to ||
      (f.species && f.species.length > 0),
  );
}

interface SearchState {
  status: "idle" | "loading" | "success" | "error";
  response: SearchResponse | null;
  error: string | null;
  lastQuery: string;
  lastFilters: FilterState;
  /** Whether the last search was filter-only (no query). */
  lastWasFilterOnly: boolean;
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<FilterState>({});
  const [state, setState] = useState<SearchState>({
    status: "idle",
    response: null,
    error: null,
    lastQuery: "",
    lastFilters: {},
    lastWasFilterOnly: false,
  });
  const inputRef = useRef<HTMLInputElement>(null);

  const runSearch = useCallback(async (q: string, f: FilterState) => {
    const trimmed = q.trim();
    const filtersActive = hasActiveFilters(f);
    if (!trimmed && !filtersActive) return;

    setState((s) => ({
      ...s,
      status: "loading",
      error: null,
      lastQuery: trimmed,
      lastFilters: f,
      lastWasFilterOnly: !trimmed,
    }));

    try {
      const response = await search({
        ...(trimmed ? { query: trimmed } : {}),
        top_k: 20,
        ...f,
      });
      setState({
        status: "success",
        response,
        error: null,
        lastQuery: trimmed,
        lastFilters: f,
        lastWasFilterOnly: !trimmed,
      });
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? `${err.status}: ${err.message}`
          : err instanceof Error
            ? err.message
            : "Unknown error";
      setState({
        status: "error",
        response: null,
        error: msg,
        lastQuery: trimmed,
        lastFilters: f,
        lastWasFilterOnly: !trimmed,
      });
    }
  }, []);

  const onSubmit = () => runSearch(query, filters);

  // Re-run when filters change:
  //  - If a query is set, always re-run with the same query.
  //  - If no query but filters are active, run in filter-only mode.
  //  - If no query and no filters, clear back to idle (don't re-fire).
  const onFilterChange = (next: FilterState) => {
    setFilters(next);
    const trimmed = query.trim();
    if (trimmed || hasActiveFilters(next)) {
      runSearch(query, next);
    } else {
      setState((s) => ({ ...s, status: "idle", response: null, error: null }));
    }
  };

  const onExample = (q: string) => {
    setQuery(q);
    runSearch(q, filters);
  };

  const filtersActiveNow = hasActiveFilters(filters);

  const resultsHeader = useMemo(() => {
    if (state.status === "success" && state.response) {
      const r = state.response;
      const filterCount =
        (state.lastFilters.doc_type ? 1 : 0) +
        (state.lastFilters.categories?.length ?? 0) +
        (state.lastFilters.jurisdiction ? 1 : 0) +
        (state.lastFilters.facility_name ? 1 : 0) +
        (state.lastFilters.date_from ? 1 : 0) +
        (state.lastFilters.date_to ? 1 : 0);

      if (state.lastWasFilterOnly) {
        return (
          <div className="flex items-baseline gap-2 font-mono text-xs text-tertiary">
            <span className="text-secondary">{r.total_results}</span>
            <span>results · filter-only · {filterCount} filter{filterCount === 1 ? "" : "s"} applied · sorted by inspection date</span>
          </div>
        );
      }
      return (
        <div className="flex items-baseline gap-2 font-mono text-xs text-tertiary">
          <span className="text-secondary">{r.total_results}</span>
          <span>results for</span>
          <span className="text-primary">&ldquo;{r.query}&rdquo;</span>
          {filterCount > 0 && (
            <span>
              · {filterCount} filter{filterCount === 1 ? "" : "s"}
            </span>
          )}
        </div>
      );
    }
    return null;
  }, [state]);

  return (
    <div className="flex h-full">
      <FilterSidebar value={filters} onChange={onFilterChange} />

      <div className="flex-1 overflow-y-auto">
        {/* Search bar */}
        <div className="sticky top-0 z-10 bg-surface-1/95 backdrop-blur border-b border-border-subtle px-8 py-5">
          <div className="max-w-4xl">
            <SearchInput
              ref={inputRef}
              value={query}
              onChange={setQuery}
              onSubmit={onSubmit}
              loading={state.status === "loading"}
              allowEmptySubmit={filtersActiveNow}
            />
            {resultsHeader && <div className="mt-3">{resultsHeader}</div>}
            {!resultsHeader && state.status === "idle" && filtersActiveNow && (
              <div className="mt-3 font-mono text-xs text-tertiary">
                Filters active — click <span className="text-accent">Apply Filters</span> or press Enter to browse.
              </div>
            )}
          </div>
        </div>

        {/* Body */}
        <div className="px-8 py-8">
          <div className="max-w-4xl space-y-3">
            {/* Idle: hero + example queries */}
            {state.status === "idle" && (
              <div className="py-12">
                <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-accent mb-3">
                  Hybrid retrieval · BM25 + vector + metadata
                </div>
                <h1 className="font-display text-4xl font-medium text-primary leading-[1.05] max-w-2xl">
                  Search the USDA APHIS animal welfare corpus.
                </h1>
                <p className="mt-4 max-w-2xl text-base text-secondary leading-[1.55]">
                  1,616 documents — inspection reports, regulations, policy
                  guidance, and enforcement actions. Results are ranked by
                  semantic similarity, full-text relevance, and metadata match,
                  with a short explanation of why the top hits are relevant.
                  You can also browse by filter alone — pick a violation
                  category or jurisdiction without typing a query.
                </p>
                <div className="mt-8">
                  <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary mb-3">
                    Try a query
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {EXAMPLE_QUERIES.map((q) => (
                      <button
                        key={q}
                        type="button"
                        onClick={() => onExample(q)}
                        className="rounded-sm border border-border-default bg-surface-2 px-3 py-1.5 text-sm text-secondary hover:border-accent hover:text-accent transition-colors"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Loading: skeleton cards */}
            {state.status === "loading" &&
              Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="surface-2 border border-border-subtle rounded-sm p-6 animate-pulse"
                  style={{ opacity: 1 - i * 0.2 }}
                >
                  <div className="flex justify-between mb-4">
                    <div className="h-3 w-32 bg-surface-3 rounded-sm" />
                    <div className="h-6 w-12 bg-surface-3 rounded-sm" />
                  </div>
                  <div className="h-5 w-2/3 bg-surface-3 rounded-sm mb-2" />
                  <div className="h-3 w-1/3 bg-surface-3 rounded-sm mb-5" />
                  <div className="space-y-2">
                    <div className="h-3 w-full bg-surface-3 rounded-sm" />
                    <div className="h-3 w-5/6 bg-surface-3 rounded-sm" />
                    <div className="h-3 w-3/4 bg-surface-3 rounded-sm" />
                  </div>
                </div>
              ))}

            {/* Error */}
            {state.status === "error" && (
              <div className="border border-critical/40 bg-critical-muted rounded-sm p-6">
                <div className="font-mono text-[10px] uppercase tracking-wider text-critical mb-2">
                  Search failed
                </div>
                <p className="text-sm text-secondary">{state.error}</p>
                <button
                  type="button"
                  onClick={() => runSearch(state.lastQuery, state.lastFilters)}
                  className="mt-4 rounded-sm border border-border-default bg-surface-2 px-3 py-1.5 text-sm text-primary hover:border-border-strong"
                >
                  Retry
                </button>
              </div>
            )}

            {/* Success: results or empty */}
            {state.status === "success" && state.response && (
              <>
                {state.response.results.length === 0 ? (
                  <div className="border border-border-subtle bg-surface-2 rounded-sm py-16 text-center">
                    <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-tertiary mb-2">
                      No matches
                    </div>
                    <div className="font-display text-xl text-primary mb-2">
                      Nothing in the corpus fits.
                    </div>
                    <p className="text-sm text-secondary max-w-md mx-auto">
                      Try broadening your query or clearing some filters. The
                      corpus is currently limited to USDA APHIS California
                      records.
                    </p>
                  </div>
                ) : (
                  state.response.results.map((r, i) => (
                    <ResultCard key={r.id} result={r} rank={i + 1} />
                  ))
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
