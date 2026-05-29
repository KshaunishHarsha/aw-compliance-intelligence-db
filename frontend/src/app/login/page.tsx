"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { ApiError, getToken, login } from "@/lib/api";

// Next.js 16 requires useSearchParams() to be inside a Suspense boundary
// during prerender. Split into an outer wrapper + inner form.
export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/search";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // If a valid token already exists, skip the form
  useEffect(() => {
    if (getToken()) router.replace(next);
  }, [next, router]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      router.replace(next);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.status === 401
            ? "Incorrect email or password."
            : err.message
          : err instanceof Error
            ? err.message
            : "Login failed";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-md">
        {/* Brand */}
        <div className="mb-10 text-center">
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-accent">
            AW · Intelligence
          </div>
          <h1 className="mt-2 font-display text-3xl font-medium text-primary">
            Compliance Archive
          </h1>
          <p className="mt-2 text-sm text-tertiary">
            Sign in to search the USDA APHIS corpus.
          </p>
        </div>

        {/* Card */}
        <form
          onSubmit={onSubmit}
          className="surface-2 border border-border-subtle rounded-sm p-6 space-y-5"
        >
          <div>
            <label
              htmlFor="email"
              className="block font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary mb-1.5"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
              className="block w-full rounded-sm border border-border-default bg-surface-1 px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-accent focus:outline-none"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="block font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary mb-1.5"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="block w-full rounded-sm border border-border-default bg-surface-1 px-3 py-2 text-sm text-primary focus:border-accent focus:outline-none"
            />
          </div>

          {error && (
            <div className="border border-critical/40 bg-critical-muted rounded-sm px-3 py-2">
              <div className="font-mono text-[10px] uppercase tracking-wider text-critical">
                Auth error
              </div>
              <div className="mt-0.5 text-xs text-secondary">{error}</div>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !email || !password}
            className="w-full rounded-sm bg-accent px-4 py-2.5 text-sm font-medium text-accent-foreground transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:bg-surface-3 disabled:text-disabled"
          >
            {submitting ? "Signing in…" : "Sign In"}
          </button>

          {process.env.NODE_ENV !== "production" && (
            <div className="border-t border-border-subtle pt-4">
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary mb-2">
                Development
              </div>
              <button
                type="button"
                onClick={() => {
                  setEmail("test@example.com");
                  setPassword("test1234");
                }}
                className="text-xs text-tertiary hover:text-accent transition-colors"
              >
                Fill seeded test credentials →
              </button>
            </div>
          )}
        </form>

        <div className="mt-8 text-center">
          <Link
            href="/design"
            className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary hover:text-accent transition-colors"
          >
            Design Reference →
          </Link>
        </div>
      </div>
    </div>
  );
}
