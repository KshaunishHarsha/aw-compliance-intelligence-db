"use client";

/**
 * Root error boundary. Catches uncaught render errors anywhere in the tree.
 * In production we don't render the stack trace to the user.
 */
import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("Unhandled application error:", error);
  }, [error]);

  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-md">
        <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-critical mb-3">
          Something went wrong
        </div>
        <h1 className="font-display text-3xl font-medium text-primary leading-[1.1]">
          The page hit an error.
        </h1>
        <p className="mt-3 text-sm text-secondary leading-[1.6]">
          The error has been logged. You can try again — if it keeps happening,
          sign out and back in, or contact the platform admin.
        </p>

        {process.env.NODE_ENV !== "production" && (
          <div className="mt-6 border border-border-default bg-surface-2 rounded-sm p-3">
            <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-1">
              Dev detail
            </div>
            <pre className="font-mono text-[11px] text-secondary whitespace-pre-wrap break-words">
              {error.message}
              {error.digest && `\nDigest: ${error.digest}`}
            </pre>
          </div>
        )}

        <div className="mt-6 flex items-center gap-2">
          <button
            type="button"
            onClick={reset}
            className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-accent-foreground hover:bg-accent-hover transition-colors"
          >
            Try again
          </button>
          <a
            href="/search"
            className="rounded-sm border border-border-default bg-surface-2 px-4 py-2 text-sm text-secondary hover:border-border-strong hover:text-primary transition-colors"
          >
            Back to search
          </a>
        </div>
      </div>
    </div>
  );
}
