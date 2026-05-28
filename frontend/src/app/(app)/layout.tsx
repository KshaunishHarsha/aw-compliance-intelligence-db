import type { ReactNode } from "react";

import { AuthGuard } from "@/components/app-shell/auth-guard";
import { Sidebar } from "@/components/app-shell/sidebar";
import { TopBar } from "@/components/app-shell/top-bar";

/**
 * App shell — wraps every authenticated page in the (app) route group.
 * Pages outside this group (e.g. /design, /login) get a bare layout.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopBar />
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </div>
    </AuthGuard>
  );
}
