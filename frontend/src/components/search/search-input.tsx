"use client";

import { forwardRef, useEffect, useRef } from "react";

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading?: boolean;
  placeholder?: string;
  /** If true, allow submit even with an empty query (e.g. filter-only mode). */
  allowEmptySubmit?: boolean;
}

export const SearchInput = forwardRef<HTMLInputElement, SearchInputProps>(
  function SearchInput(
    { value, onChange, onSubmit, loading, placeholder, allowEmptySubmit },
    ref,
  ) {
    const innerRef = useRef<HTMLInputElement>(null);
    const inputRef = (ref as React.RefObject<HTMLInputElement>) ?? innerRef;

    // Global "/" shortcut to focus the search input (Bloomberg/Algolia-style)
    useEffect(() => {
      function onKey(e: KeyboardEvent) {
        const target = e.target as HTMLElement | null;
        if (
          e.key === "/" &&
          target?.tagName !== "INPUT" &&
          target?.tagName !== "TEXTAREA"
        ) {
          e.preventDefault();
          inputRef.current?.focus();
          inputRef.current?.select();
        }
      }
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }, [inputRef]);

    return (
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
        className="relative"
      >
        <div className="pointer-events-none absolute inset-y-0 left-4 flex items-center font-mono text-tertiary text-base">
          ⌕
        </div>
        <input
          ref={inputRef}
          type="search"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={
            placeholder ??
            "Search the corpus — facility names, violations, citations, species…"
          }
          autoComplete="off"
          spellCheck={false}
          className="block w-full rounded-sm border border-border-default bg-surface-2 pl-11 pr-32 py-3.5 text-base text-primary placeholder:text-tertiary focus:border-accent focus:outline-none"
        />

        <div className="absolute inset-y-0 right-3 flex items-center gap-2">
          {loading ? (
            <span
              className="h-2 w-2 rounded-full bg-accent"
              style={{ animation: "pulse 1.4s ease-in-out infinite" }}
              aria-label="Searching"
            />
          ) : null}
          <button
            type="submit"
            disabled={loading || (!value.trim() && !allowEmptySubmit)}
            className="rounded-sm bg-accent px-4 py-1.5 text-sm font-medium text-accent-foreground transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:bg-surface-3 disabled:text-disabled"
          >
            {!value.trim() && allowEmptySubmit ? "Apply Filters" : "Search"}
          </button>
        </div>

        <style jsx>{`
          @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.3; transform: scale(0.8); }
          }
        `}</style>
      </form>
    );
  },
);
