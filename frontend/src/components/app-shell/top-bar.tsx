"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { clearSession, getStoredEmail } from "@/lib/api";

export function TopBar({ title }: { title?: string }) {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    setEmail(getStoredEmail());
  }, []);

  const onLogout = () => {
    clearSession();
    router.replace("/login");
  };

  // Initial of the email's local part — "T" for "test@example.com"
  const initial = (email?.charAt(0) ?? "?").toUpperCase();

  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-border-subtle bg-surface-1 px-6">
      <div className="flex items-center gap-4">
        {title && (
          <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-tertiary">
            {title}
          </span>
        )}
      </div>

      <div className="flex items-center gap-4">
        {/* Keyboard hint */}
        <div className="hidden md:flex items-center gap-2 text-xs text-tertiary">
          <span>Press</span>
          <kbd className="font-mono text-[10px] border border-border-default bg-surface-2 rounded-sm px-1.5 py-0.5 text-secondary">
            /
          </kbd>
          <span>to focus search</span>
        </div>

        {/* Account */}
        <div className="flex items-center gap-2 border-l border-border-subtle pl-4">
          <div className="h-6 w-6 rounded-sm bg-accent-muted border border-accent/40 flex items-center justify-center font-mono text-[10px] text-accent">
            {initial}
          </div>
          <span className="text-xs text-secondary">{email ?? "—"}</span>
          <button
            type="button"
            onClick={onLogout}
            className="ml-2 font-mono text-[10px] uppercase tracking-wider text-tertiary hover:text-accent transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
