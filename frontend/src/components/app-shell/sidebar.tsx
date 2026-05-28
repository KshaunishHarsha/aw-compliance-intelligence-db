"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

interface NavItem {
  label: string;
  href: string;
  icon: ReactNode;
  active?: (pathname: string) => boolean;
  disabled?: boolean;
  badge?: string;
}

const NAV: NavItem[] = [
  {
    label: "Search",
    href: "/search",
    active: (p) => p === "/search" || p.startsWith("/search/"),
    icon: (
      <svg
        viewBox="0 0 16 16"
        fill="none"
        className="h-4 w-4"
        aria-hidden
      >
        <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.25" />
        <path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    label: "Documents",
    href: "/documents",
    active: (p) => p === "/documents" || p.startsWith("/documents/"),
    icon: (
      <svg viewBox="0 0 16 16" fill="none" className="h-4 w-4" aria-hidden>
        <path
          d="M3 2.5h6.5L13 6v7.5a1 1 0 01-1 1H3a1 1 0 01-1-1v-10a1 1 0 011-1z"
          stroke="currentColor"
          strokeWidth="1.25"
          strokeLinejoin="round"
        />
        <path d="M9 2.5V6h4" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    label: "Chat",
    href: "/chat",
    active: (p) => p.startsWith("/chat"),
    disabled: true,
    badge: "Phase 6",
    icon: (
      <svg viewBox="0 0 16 16" fill="none" className="h-4 w-4" aria-hidden>
        <path
          d="M2 4a1.5 1.5 0 011.5-1.5h9A1.5 1.5 0 0114 4v6a1.5 1.5 0 01-1.5 1.5H6L3 14v-2.5h-.5A1.5 1.5 0 011 10V4z"
          stroke="currentColor"
          strokeWidth="1.25"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
];

export function Sidebar() {
  const pathname = usePathname() ?? "";

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-border-subtle bg-surface-2">
      {/* Brand */}
      <div className="border-b border-border-subtle px-5 py-5">
        <Link href="/search" className="block">
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-accent">
            AW · Intelligence
          </div>
          <div className="mt-1 font-display text-base font-medium leading-tight text-primary">
            Compliance Archive
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary px-2 mb-2">
          Workspace
        </div>
        <ul className="space-y-0.5">
          {NAV.map((item) => {
            const active = item.active?.(pathname) ?? false;
            const baseClasses =
              "flex items-center gap-3 rounded-sm px-2.5 py-2 text-sm transition-colors";
            if (item.disabled) {
              return (
                <li key={item.href}>
                  <span
                    className={`${baseClasses} cursor-not-allowed text-disabled`}
                    aria-disabled
                  >
                    {item.icon}
                    <span className="flex-1">{item.label}</span>
                    {item.badge && (
                      <span className="font-mono text-[9px] uppercase tracking-wider text-tertiary border border-border-subtle rounded-sm px-1.5 py-0.5">
                        {item.badge}
                      </span>
                    )}
                  </span>
                </li>
              );
            }
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`${baseClasses} ${
                    active
                      ? "bg-accent-muted text-accent"
                      : "text-secondary hover:bg-surface-3 hover:text-primary"
                  }`}
                >
                  {item.icon}
                  <span className="flex-1">{item.label}</span>
                  {active && (
                    <span className="h-1 w-1 rounded-full bg-accent" aria-hidden />
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer — version stamp */}
      <div className="border-t border-border-subtle px-5 py-4">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary">
          Corpus
        </div>
        <div className="mt-1 font-mono text-xs text-secondary">
          1,616 documents
        </div>
        <div className="font-mono text-[10px] text-tertiary">
          USDA APHIS · 9 CFR Title 9
        </div>
      </div>
    </aside>
  );
}
