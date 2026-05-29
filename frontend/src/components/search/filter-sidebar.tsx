"use client";

import { useState } from "react";

import type {
  DocType,
  SearchRequest,
  ViolationCategory,
} from "@/lib/api";

export type FilterState = Pick<
  SearchRequest,
  | "doc_type"
  | "categories"
  | "jurisdiction"
  | "facility_name"
  | "species"
  | "date_from"
  | "date_to"
>;

interface FilterSidebarProps {
  value: FilterState;
  onChange: (next: FilterState) => void;
}

const DOC_TYPES: { value: DocType; label: string }[] = [
  { value: "inspection_report", label: "Inspection Reports" },
  { value: "regulation", label: "Regulations" },
  { value: "policy", label: "Policy" },
  { value: "enforcement_action", label: "Enforcement" },
];

const CATEGORIES: { value: ViolationCategory; label: string }[] = [
  { value: "veterinary_care", label: "Veterinary Care" },
  { value: "housing", label: "Housing" },
  { value: "sanitation", label: "Sanitation" },
  { value: "water_access", label: "Water Access" },
  { value: "feeding", label: "Feeding" },
  { value: "handling", label: "Handling" },
  { value: "overcrowding", label: "Overcrowding" },
  { value: "transport_conditions", label: "Transport" },
  { value: "recordkeeping", label: "Recordkeeping" },
  { value: "euthanasia", label: "Euthanasia" },
];

function FilterGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-b border-border-subtle pb-5 last:border-b-0">
      <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary mb-3">
        {label}
      </div>
      {children}
    </div>
  );
}

export function FilterSidebar({ value, onChange }: FilterSidebarProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const toggleCategory = (cat: ViolationCategory) => {
    const current = value.categories ?? [];
    const next = current.includes(cat)
      ? current.filter((c) => c !== cat)
      : [...current, cat];
    onChange({ ...value, categories: next.length ? next : undefined });
  };

  const setDocType = (dt: DocType | undefined) => {
    onChange({ ...value, doc_type: dt });
  };

  const activeCount =
    (value.doc_type ? 1 : 0) +
    (value.categories?.length ?? 0) +
    (value.jurisdiction ? 1 : 0) +
    (value.facility_name ? 1 : 0) +
    (value.date_from ? 1 : 0) +
    (value.date_to ? 1 : 0);

  return (
    <aside className="w-72 shrink-0 border-r border-border-subtle bg-surface-1 overflow-y-auto">
      <div className="px-6 py-5 border-b border-border-subtle flex items-center justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary">
            Filters
          </div>
          <div className="font-display text-lg font-medium text-primary mt-0.5">
            Refine
            {activeCount > 0 && (
              <span className="ml-2 font-mono text-xs text-accent">
                · {activeCount} active
              </span>
            )}
          </div>
        </div>
        {activeCount > 0 && (
          <button
            type="button"
            onClick={() => onChange({})}
            className="text-xs text-tertiary hover:text-accent transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      <div className="px-6 py-5 space-y-5">
        {/* Document Type */}
        <FilterGroup label="Document Type">
          <div className="space-y-1">
            {DOC_TYPES.map((dt) => {
              const active = value.doc_type === dt.value;
              return (
                <button
                  key={dt.value}
                  type="button"
                  onClick={() => setDocType(active ? undefined : dt.value)}
                  className={`flex w-full items-center justify-between rounded-sm px-2.5 py-1.5 text-sm text-left transition-colors ${
                    active
                      ? "bg-accent-muted text-accent border border-accent/40"
                      : "text-secondary border border-transparent hover:bg-surface-2 hover:text-primary"
                  }`}
                >
                  <span>{dt.label}</span>
                  {active && <span className="font-mono text-xs">✓</span>}
                </button>
              );
            })}
          </div>
        </FilterGroup>

        {/* Categories — OR logic */}
        <FilterGroup label="Violation Categories">
          <div className="text-[10px] text-tertiary mb-2">Any selected · OR</div>
          <div className="flex flex-wrap gap-1.5">
            {CATEGORIES.map((cat) => {
              const active = (value.categories ?? []).includes(cat.value);
              return (
                <button
                  key={cat.value}
                  type="button"
                  onClick={() => toggleCategory(cat.value)}
                  className={`rounded-sm border px-2 py-1 font-mono text-[11px] uppercase tracking-wider transition-colors ${
                    active
                      ? "bg-accent-muted text-accent border-accent/40"
                      : "border-border-default text-secondary hover:border-border-strong hover:text-primary"
                  }`}
                >
                  {cat.label}
                </button>
              );
            })}
          </div>
        </FilterGroup>

        {/* Jurisdiction */}
        <FilterGroup label="Jurisdiction">
          <input
            type="text"
            placeholder="2-letter state code (CA)"
            value={value.jurisdiction ?? ""}
            onChange={(e) =>
              onChange({
                ...value,
                jurisdiction: e.target.value || undefined,
              })
            }
            maxLength={2}
            className="block w-full rounded-sm border border-border-default bg-surface-2 px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-accent focus:outline-none uppercase"
          />
        </FilterGroup>

        {/* Date range */}
        <FilterGroup label="Inspection Date">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[10px] text-tertiary mb-1">
                From
              </label>
              <input
                type="date"
                value={value.date_from ?? ""}
                onChange={(e) =>
                  onChange({
                    ...value,
                    date_from: e.target.value || undefined,
                  })
                }
                className="block w-full rounded-sm border border-border-default bg-surface-2 px-2 py-1.5 text-xs text-primary focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-[10px] text-tertiary mb-1">
                To
              </label>
              <input
                type="date"
                value={value.date_to ?? ""}
                onChange={(e) =>
                  onChange({ ...value, date_to: e.target.value || undefined })
                }
                className="block w-full rounded-sm border border-border-default bg-surface-2 px-2 py-1.5 text-xs text-primary focus:border-accent focus:outline-none"
              />
            </div>
          </div>
        </FilterGroup>

        {/* Advanced — collapsed by default */}
        <div>
          <button
            type="button"
            onClick={() => setShowAdvanced((s) => !s)}
            className="flex w-full items-center justify-between font-mono text-[10px] uppercase tracking-[0.18em] text-tertiary hover:text-secondary transition-colors py-1"
          >
            <span>Advanced</span>
            <span>{showAdvanced ? "−" : "+"}</span>
          </button>
          {showAdvanced && (
            <div className="mt-3 space-y-3">
              <div>
                <label className="block text-[10px] text-tertiary mb-1">
                  Facility name (partial match)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Lucky Rabbits"
                  value={value.facility_name ?? ""}
                  onChange={(e) =>
                    onChange({
                      ...value,
                      facility_name: e.target.value || undefined,
                    })
                  }
                  className="block w-full rounded-sm border border-border-default bg-surface-2 px-2.5 py-1.5 text-xs text-primary placeholder:text-tertiary focus:border-accent focus:outline-none"
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
