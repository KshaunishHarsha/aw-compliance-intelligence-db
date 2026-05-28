/**
 * Design Reference — living style guide for the AW Compliance Intelligence
 * Platform. Every token, primitive, and pattern shown in context. This page
 * has no app chrome (no nav, no header) by design; it is a working reference
 * for developers building pages on top of the design system.
 */

import type { ReactNode } from "react";

// ────────────────────────────────────────────────────────────────────────────
// Helpers — local primitives. Not the real component library; these exist
// only so the reference page itself is composed using tokens, not bespoke CSS.

function Section({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="relative border-t border-border-subtle py-16">
      <div className="mb-10 grid grid-cols-12 gap-x-6">
        <div className="col-span-12 md:col-span-3">
          <span className="font-mono text-xs uppercase tracking-[0.18em] text-accent">
            {eyebrow}
          </span>
        </div>
        <div className="col-span-12 md:col-span-9">
          <h2 className="font-display text-3xl font-medium text-primary">
            {title}
          </h2>
          {description && (
            <p className="mt-3 max-w-2xl text-base text-secondary">
              {description}
            </p>
          )}
        </div>
      </div>
      <div className="grid grid-cols-12 gap-x-6 gap-y-6">{children}</div>
    </section>
  );
}

function Swatch({
  name,
  value,
  cssVar,
  textOn,
  border = false,
}: {
  name: string;
  value: string;
  cssVar: string;
  textOn?: "light" | "dark";
  border?: boolean;
}) {
  return (
    <div className="flex flex-col">
      <div
        className={`h-20 ${
          border ? "border border-border-default" : ""
        } rounded-sm`}
        style={{ background: value }}
      >
        {textOn && (
          <div className="flex h-full items-center justify-center">
            <span
              className="font-mono text-xs"
              style={{
                color: textOn === "light" ? "#F5F1EB" : "#14110F",
              }}
            >
              Aa
            </span>
          </div>
        )}
      </div>
      <div className="mt-2 flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium text-primary">{name}</span>
        <span className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
          {value}
        </span>
      </div>
      <span className="font-mono text-[10px] text-tertiary/70">{cssVar}</span>
    </div>
  );
}

function Tag({
  children,
  tone = "default",
}: {
  children: ReactNode;
  tone?: "default" | "accent" | "critical" | "warning" | "info" | "success";
}) {
  const tones: Record<string, string> = {
    default:
      "bg-surface-3 text-secondary border-border-default",
    accent:
      "bg-accent-muted text-accent border-accent/30",
    critical:
      "bg-critical-muted text-critical border-critical/30",
    warning:
      "bg-warning-muted text-warning border-warning/30",
    info: "bg-info-muted text-info border-info/30",
    success:
      "bg-success-muted text-success border-success/30",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

function StatusDot({ tone }: { tone: "critical" | "warning" | "info" | "success" }) {
  const colors: Record<string, string> = {
    critical: "var(--status-critical-text)",
    warning: "var(--status-warning-text)",
    info: "var(--status-info-text)",
    success: "var(--status-success-text)",
  };
  return (
    <span
      className="inline-block h-2 w-2 rounded-full"
      style={{
        background: colors[tone],
        boxShadow: `0 0 0 3px ${colors[tone]}22`,
      }}
    />
  );
}

function MetaRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline gap-3 border-b border-border-subtle py-2 last:border-b-0">
      <span className="font-mono text-[11px] uppercase tracking-wider text-tertiary min-w-[140px]">
        {label}
      </span>
      <span className="text-sm text-primary">{value}</span>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Page

export default function DesignReferencePage() {
  return (
    <main className="relative z-10 mx-auto max-w-[1280px] px-8 py-16">
      {/* Header */}
      <header className="grid grid-cols-12 gap-x-6 pb-12">
        <div className="col-span-12 md:col-span-3">
          <div className="font-mono text-xs uppercase tracking-[0.2em] text-accent">
            Internal · v1.0
          </div>
          <div className="mt-1 font-mono text-[11px] text-tertiary">
            /design
          </div>
        </div>
        <div className="col-span-12 md:col-span-9">
          <h1 className="font-display text-4xl font-medium leading-[1.05] text-primary">
            Design System Reference
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-secondary">
            The visual language of the Animal Welfare Compliance Intelligence
            Platform — tokens, type, and primitives, in context. Built for
            investigators, compliance analysts, and legal researchers working
            against the USDA APHIS corpus.
          </p>
        </div>
      </header>

      {/* ───────────────────── Typography ───────────────────── */}
      <Section
        eyebrow="01 · Type"
        title="Typography"
        description="Fraunces for editorial headings (variable, with characterful wedge serifs), IBM Plex Sans for UI and body, IBM Plex Mono for citations and reference numbers. The mix is deliberate: prose reads like a serious publication, data reads like a document."
      >
        <div className="col-span-12 lg:col-span-8 space-y-8">
          <div>
            <span className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
              Display · Fraunces · 48 / 1.05
            </span>
            <div className="mt-2 font-display text-4xl font-medium leading-[1.05] text-primary">
              USDA Inspection Report — Facility Non-Compliance Summary
            </div>
          </div>

          <div>
            <span className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
              H1 · Fraunces · 36 / 1.1
            </span>
            <div className="mt-2 font-display text-3xl font-medium leading-[1.1] text-primary">
              Repeat violations of attending veterinarian standards
            </div>
          </div>

          <div>
            <span className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
              H2 · Fraunces · 28 / 1.2
            </span>
            <div className="mt-2 font-display text-2xl font-medium leading-[1.2] text-primary">
              Subpart D — Veterinary Care
            </div>
          </div>

          <div>
            <span className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
              H3 · Plex Sans Semibold · 22 / 1.3
            </span>
            <div className="mt-2 text-xl font-semibold leading-[1.3] text-primary">
              Findings — Lucky Rabbits Inc., March 11 2024
            </div>
          </div>

          <div>
            <span className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
              H4 · Plex Sans Medium · 17 / 1.4
            </span>
            <div className="mt-2 text-lg font-medium leading-[1.4] text-primary">
              Citation Detail
            </div>
          </div>

          <div>
            <span className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
              H5 · Plex Sans Medium · 15 / 1.5
            </span>
            <div className="mt-2 text-base font-medium leading-[1.5] text-primary">
              Inspector notes
            </div>
          </div>

          <div className="border-t border-border-subtle pt-8">
            <span className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
              Body · Plex Sans · 15 / 1.55
            </span>
            <p className="mt-2 max-w-2xl text-base leading-[1.55] text-secondary">
              A routine USDA APHIS inspection of Lucky Rabbits Inc. (cert.{" "}
              <span className="font-mono text-primary">93-B-0242</span>, CA) on
              July 11 2016 identified repeat violations under{" "}
              <span className="font-mono text-primary">9 CFR §3.50(a)</span>,{" "}
              <span className="font-mono text-primary">§3.51(d)</span>, and{" "}
              <span className="font-mono text-primary">§3.53</span> related to
              uncovered light bulbs over enclosures, rusted housing structures,
              and damaged wire floors that could injure the rabbits.
            </p>
          </div>

          <div>
            <span className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
              Small · Plex Sans · 13 / 1.5
            </span>
            <p className="mt-2 max-w-2xl text-sm leading-[1.5] text-tertiary">
              Original correction deadline February 28 2026 — facility moved
              out of registered site without notification under 9 CFR
              §2.30(c)(1).
            </p>
          </div>

          <div>
            <span className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
              Caption · Plex Sans · 12
            </span>
            <p className="mt-2 text-xs text-tertiary">
              Source: APHIS Animal Care Inspection Report, June 2024
            </p>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4 space-y-4">
          <div className="surface-2 border border-border-subtle p-5 rounded-sm">
            <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-3">
              Citation Specimen
            </div>
            <div className="space-y-2">
              <div className="font-mono text-sm text-primary">
                9 CFR § 3.131(c)
              </div>
              <div className="font-mono text-sm text-primary">
                AWA Docket No. 25-J-0069
              </div>
              <div className="font-mono text-sm text-primary">93-C-0119</div>
              <div className="font-mono text-sm text-primary">
                §2.40(b)(2), §3.81
              </div>
            </div>
          </div>

          <div className="surface-2 border border-border-subtle p-5 rounded-sm">
            <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-3">
              Label & Caption Scale
            </div>
            <div className="space-y-3">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary">
                  Eyebrow / overline
                </div>
              </div>
              <div>
                <div className="text-xs font-medium text-secondary">
                  Section caption
                </div>
              </div>
              <div>
                <div className="text-xs text-tertiary">
                  Helper text / placeholder
                </div>
              </div>
            </div>
          </div>
        </div>
      </Section>

      {/* ───────────────────── Color ───────────────────── */}
      <Section
        eyebrow="02 · Color"
        title="Color tokens"
        description="Warm dark surfaces with brown undertone, four levels of text contrast, a deep amber accent reserved for action and emphasis, and four status colors that meet WCAG AA against the page background."
      >
        <div className="col-span-12">
          <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-3">
            Surfaces
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Swatch
              name="surface-1"
              value="#14110F"
              cssVar="--surface-1"
              textOn="light"
              border
            />
            <Swatch
              name="surface-2"
              value="#1C1916"
              cssVar="--surface-2"
              textOn="light"
              border
            />
            <Swatch
              name="surface-3"
              value="#252220"
              cssVar="--surface-3"
              textOn="light"
              border
            />
          </div>
        </div>

        <div className="col-span-12">
          <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-3 mt-4">
            Borders
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Swatch name="border-subtle" value="#2A2622" cssVar="--border-subtle" border />
            <Swatch name="border-default" value="#3A332D" cssVar="--border-default" border />
            <Swatch name="border-strong" value="#4D4439" cssVar="--border-strong" border />
          </div>
        </div>

        <div className="col-span-12">
          <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-3 mt-4">
            Text hierarchy
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Swatch name="text-primary" value="#F5F1EB" cssVar="--text-primary" textOn="dark" />
            <Swatch name="text-secondary" value="#B8B0A7" cssVar="--text-secondary" textOn="dark" />
            <Swatch name="text-tertiary" value="#8A8278" cssVar="--text-tertiary" textOn="dark" />
            <Swatch name="text-disabled" value="#5A554D" cssVar="--text-disabled" textOn="dark" />
          </div>
        </div>

        <div className="col-span-12">
          <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-3 mt-4">
            Accent — muted amber
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Swatch name="accent-default" value="#B8842C" cssVar="--accent-default" textOn="dark" />
            <Swatch name="accent-hover" value="#D49B3D" cssVar="--accent-hover" textOn="dark" />
            <Swatch name="accent-muted" value="#3D2D14" cssVar="--accent-muted" border />
          </div>
        </div>

        <div className="col-span-12">
          <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-3 mt-4">
            Status — for violation severity & document processing
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="space-y-3">
              <Swatch name="critical" value="#E26B6B" cssVar="--status-critical-text" />
              <Swatch name="critical-muted" value="#3A1818" cssVar="--status-critical-muted" border />
              <div className="flex items-center gap-2">
                <StatusDot tone="critical" />
                <span className="text-sm" style={{ color: "var(--status-critical-text)" }}>
                  Critical Violation
                </span>
              </div>
            </div>
            <div className="space-y-3">
              <Swatch name="warning" value="#D4A574" cssVar="--status-warning-text" />
              <Swatch name="warning-muted" value="#3A2A14" cssVar="--status-warning-muted" border />
              <div className="flex items-center gap-2">
                <StatusDot tone="warning" />
                <span className="text-sm" style={{ color: "var(--status-warning-text)" }}>
                  Non-Critical
                </span>
              </div>
            </div>
            <div className="space-y-3">
              <Swatch name="info" value="#8FA8C5" cssVar="--status-info-text" />
              <Swatch name="info-muted" value="#1A2330" cssVar="--status-info-muted" border />
              <div className="flex items-center gap-2">
                <StatusDot tone="info" />
                <span className="text-sm" style={{ color: "var(--status-info-text)" }}>
                  Inspection Pending
                </span>
              </div>
            </div>
            <div className="space-y-3">
              <Swatch name="success" value="#7FA679" cssVar="--status-success-text" />
              <Swatch name="success-muted" value="#1A2A1A" cssVar="--status-success-muted" border />
              <div className="flex items-center gap-2">
                <StatusDot tone="success" />
                <span className="text-sm" style={{ color: "var(--status-success-text)" }}>
                  No Findings
                </span>
              </div>
            </div>
          </div>
        </div>
      </Section>

      {/* ───────────────────── Primitives ───────────────────── */}
      <Section
        eyebrow="03 · Primitives"
        title="Component primitives"
        description="Unstyled building blocks — tags, status indicators, metadata rows, buttons, inputs. Pages compose these; they are not themselves pages."
      >
        {/* Tags / Badges */}
        <div className="col-span-12">
          <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-3">
            Tags · violation categories
          </div>
          <div className="flex flex-wrap gap-2">
            <Tag>Water Access</Tag>
            <Tag>Transport Conditions</Tag>
            <Tag>Veterinary Care</Tag>
            <Tag>Sanitation</Tag>
            <Tag>Housing</Tag>
            <Tag>Recordkeeping</Tag>
            <Tag>Overcrowding</Tag>
            <Tag tone="accent">Selected Filter</Tag>
          </div>
        </div>

        {/* Status indicators */}
        <div className="col-span-12 md:col-span-6">
          <div className="surface-2 border border-border-subtle p-5 rounded-sm">
            <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-4">
              Document processing status
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-secondary">Ingestion</span>
                <div className="flex items-center gap-2">
                  <StatusDot tone="success" />
                  <span className="text-sm" style={{ color: "var(--status-success-text)" }}>
                    Complete
                  </span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-secondary">Embedding</span>
                <div className="flex items-center gap-2">
                  <StatusDot tone="info" />
                  <span className="text-sm" style={{ color: "var(--status-info-text)" }}>
                    Processing
                  </span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-secondary">OCR extraction</span>
                <div className="flex items-center gap-2">
                  <StatusDot tone="warning" />
                  <span className="text-sm" style={{ color: "var(--status-warning-text)" }}>
                    Retrying
                  </span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-secondary">Classification</span>
                <div className="flex items-center gap-2">
                  <StatusDot tone="critical" />
                  <span className="text-sm" style={{ color: "var(--status-critical-text)" }}>
                    Failed
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Metadata rows */}
        <div className="col-span-12 md:col-span-6">
          <div className="surface-2 border border-border-subtle p-5 rounded-sm">
            <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-4">
              Document metadata panel
            </div>
            <MetaRow label="Facility" value="Lucky Rabbits Inc." />
            <MetaRow label="Jurisdiction" value="California" />
            <MetaRow
              label="Inspection Date"
              value="July 11, 2016"
            />
            <MetaRow
              label="Certificate"
              value={<span className="font-mono">93-B-0242</span>}
            />
            <MetaRow label="Inspector" value="Tyler Fields, DVM" />
            <MetaRow
              label="Species"
              value="Rabbits, Guinea Pigs"
            />
          </div>
        </div>

        {/* Button hierarchy */}
        <div className="col-span-12">
          <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-3">
            Button hierarchy
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {/* Primary */}
            <button
              type="button"
              className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-accent-foreground transition-colors hover:bg-accent-hover"
            >
              Run Search
            </button>
            {/* Secondary */}
            <button
              type="button"
              className="rounded-sm border border-border-default bg-surface-2 px-4 py-2 text-sm font-medium text-primary transition-colors hover:border-border-strong hover:bg-surface-3"
            >
              Clear Filters
            </button>
            {/* Ghost */}
            <button
              type="button"
              className="rounded-sm px-4 py-2 text-sm font-medium text-secondary transition-colors hover:bg-surface-2 hover:text-primary"
            >
              Cancel
            </button>
            {/* Destructive */}
            <button
              type="button"
              className="rounded-sm border border-critical/40 bg-critical-muted px-4 py-2 text-sm font-medium text-critical transition-colors hover:border-critical/70"
            >
              Delete Document
            </button>
            {/* Disabled */}
            <button
              type="button"
              disabled
              className="rounded-sm border border-border-subtle bg-surface-2 px-4 py-2 text-sm font-medium text-disabled cursor-not-allowed"
            >
              Disabled
            </button>
          </div>
        </div>

        {/* Inputs */}
        <div className="col-span-12 md:col-span-6">
          <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-3">
            Text input
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-secondary">
              Facility name
            </label>
            <input
              type="text"
              placeholder="e.g. Lucky Rabbits Inc."
              defaultValue=""
              className="block w-full rounded-sm border border-border-default bg-surface-2 px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-accent focus:outline-none"
            />
          </div>
        </div>

        <div className="col-span-12 md:col-span-6">
          <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-3">
            Search input
          </div>
          <div className="relative">
            <div className="pointer-events-none absolute inset-y-0 left-3 flex items-center font-mono text-tertiary text-sm">
              ⌕
            </div>
            <input
              type="search"
              placeholder="Search the corpus — facilities, species, citations…"
              className="block w-full rounded-sm border border-border-default bg-surface-2 pl-10 pr-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-accent focus:outline-none"
            />
          </div>
        </div>

        {/* Divider */}
        <div className="col-span-12">
          <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-3">
            Dividers
          </div>
          <div className="space-y-6">
            <div>
              <div className="text-sm text-secondary">Before</div>
              <hr className="my-3 border-border-subtle" />
              <div className="text-sm text-secondary">After (subtle)</div>
            </div>
            <div>
              <div className="text-sm text-secondary">Before</div>
              <hr className="my-3 border-border-default" />
              <div className="text-sm text-secondary">After (default)</div>
            </div>
          </div>
        </div>
      </Section>

      {/* ───────────────────── Spacing & Grid ───────────────────── */}
      <Section
        eyebrow="04 · Layout"
        title="Spacing & grid"
        description="The 12-column grid powers every page. Spacing follows Tailwind's default 4px scale. Density is preferred over generosity — this is a research tool, not a marketing site."
      >
        <div className="col-span-12">
          <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-3">
            Spacing scale · 4px base
          </div>
          <div className="space-y-2">
            {[
              { token: "1", px: 4 },
              { token: "2", px: 8 },
              { token: "3", px: 12 },
              { token: "4", px: 16 },
              { token: "6", px: 24 },
              { token: "8", px: 32 },
              { token: "12", px: 48 },
              { token: "16", px: 64 },
            ].map(({ token, px }) => (
              <div key={token} className="flex items-center gap-4">
                <div className="font-mono text-xs text-tertiary w-12">{token}</div>
                <div className="font-mono text-[10px] text-tertiary w-12">
                  {px}px
                </div>
                <div
                  className="h-2 bg-accent-muted border border-accent/40 rounded-sm"
                  style={{ width: `${px}px` }}
                />
              </div>
            ))}
          </div>
        </div>

        <div className="col-span-12">
          <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary mb-3 mt-4">
            12-column grid
          </div>
          <div className="grid grid-cols-12 gap-3">
            {Array.from({ length: 12 }).map((_, i) => (
              <div
                key={i}
                className="h-16 bg-surface-2 border border-border-subtle rounded-sm flex items-center justify-center font-mono text-[10px] text-tertiary"
              >
                {i + 1}
              </div>
            ))}
          </div>

          <div className="mt-6 grid grid-cols-12 gap-3">
            <div className="col-span-3 h-12 bg-accent-muted border border-accent/40 rounded-sm flex items-center justify-center font-mono text-[10px] text-accent">
              col-span-3
            </div>
            <div className="col-span-9 h-12 bg-surface-2 border border-border-default rounded-sm flex items-center justify-center font-mono text-[10px] text-secondary">
              col-span-9
            </div>
          </div>

          <div className="mt-3 grid grid-cols-12 gap-3">
            <div className="col-span-4 h-12 bg-accent-muted border border-accent/40 rounded-sm flex items-center justify-center font-mono text-[10px] text-accent">
              col-span-4
            </div>
            <div className="col-span-4 h-12 bg-surface-2 border border-border-default rounded-sm flex items-center justify-center font-mono text-[10px] text-secondary">
              col-span-4
            </div>
            <div className="col-span-4 h-12 bg-surface-2 border border-border-default rounded-sm flex items-center justify-center font-mono text-[10px] text-secondary">
              col-span-4
            </div>
          </div>
        </div>
      </Section>

      {/* ───────────────────── Composition example ───────────────────── */}
      <Section
        eyebrow="05 · In Context"
        title="Composition example"
        description="A representative search result card — pulling together typography, color, tags, status, metadata, and citations as they will appear in production."
      >
        <article className="col-span-12 surface-2 border border-border-subtle rounded-sm">
          <div className="border-b border-border-subtle p-6">
            <div className="flex items-start justify-between gap-6">
              <div>
                <div className="flex items-center gap-3 mb-3">
                  <Tag tone="accent">Inspection Report</Tag>
                  <Tag tone="critical">Repeat Violation</Tag>
                  <div className="flex items-center gap-2">
                    <StatusDot tone="warning" />
                    <span className="font-mono text-[11px] uppercase tracking-wider text-warning">
                      Open
                    </span>
                  </div>
                </div>
                <h3 className="font-display text-2xl font-medium text-primary leading-[1.2]">
                  Lucky Rabbits Inc. — Repeat violations of housing standards
                </h3>
                <div className="mt-2 flex items-center gap-3 font-mono text-xs text-tertiary">
                  <span>93-B-0242</span>
                  <span>·</span>
                  <span>California</span>
                  <span>·</span>
                  <span>2016-07-11</span>
                </div>
              </div>
              <div className="text-right">
                <div className="font-mono text-[10px] uppercase tracking-wider text-tertiary">
                  Match Score
                </div>
                <div className="font-display text-3xl font-medium text-accent">
                  0.87
                </div>
                <div className="font-mono text-[10px] text-tertiary">
                  v: 0.91 · bm25: 0.74
                </div>
              </div>
            </div>
          </div>

          <div className="p-6 space-y-4">
            <p className="text-base text-secondary leading-[1.55]">
              A routine USDA APHIS inspection identified repeat violations under{" "}
              <span className="font-mono text-primary">9 CFR §3.50(a)</span>,{" "}
              <span className="font-mono text-primary">§3.51(d)</span>, and{" "}
              <span className="font-mono text-primary">§3.53</span> related to
              uncovered light bulbs over enclosures, rusted housing structures,
              and damaged wire floors that could injure the rabbits. Original
              correction deadlines had passed without full resolution.
            </p>

            <div className="border-l-2 border-accent pl-4 py-1 bg-accent-muted/30">
              <div className="font-mono text-[10px] uppercase tracking-wider text-accent mb-1">
                Why this matched
              </div>
              <p className="text-sm text-secondary">
                Document contains repeat violations of housing standards for
                rabbits — matches the query terms{" "}
                <span className="text-primary">housing</span> and{" "}
                <span className="text-primary">rabbit enclosures</span>, with
                strong overlap on cited CFR sections in <Tag>Housing</Tag>{" "}
                <Tag>Sanitation</Tag>.
              </p>
            </div>
          </div>
        </article>
      </Section>

      {/* Footer */}
      <footer className="border-t border-border-subtle mt-16 pt-8 pb-16">
        <div className="grid grid-cols-12 gap-x-6">
          <div className="col-span-12 md:col-span-3">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-tertiary">
              End of reference
            </div>
          </div>
          <div className="col-span-12 md:col-span-9">
            <p className="text-sm text-tertiary max-w-2xl">
              All tokens defined in{" "}
              <span className="font-mono text-secondary">
                src/app/globals.css
              </span>
              . Fonts loaded via{" "}
              <span className="font-mono text-secondary">next/font/google</span>{" "}
              in{" "}
              <span className="font-mono text-secondary">
                src/app/layout.tsx
              </span>
              . No external UI libraries — Tailwind v4 with the custom token
              system only.
            </p>
          </div>
        </div>
      </footer>
    </main>
  );
}
