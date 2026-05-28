"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { getToken } from "@/lib/api";

/**
 * Client-side auth gate. If no token is present, bounces to /login?next=<here>.
 * Renders nothing until the check completes to avoid a flash of authed UI.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (getToken()) {
      setChecked(true);
    } else {
      const next = encodeURIComponent(pathname);
      router.replace(`/login?next=${next}`);
    }
  }, [router, pathname]);

  if (!checked) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-tertiary">
          Checking session…
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
