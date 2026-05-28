"use client";

import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// PDF.js worker — served from a public CDN to avoid Turbopack worker bundling
// gotchas. Pinned to the exact pdfjs version react-pdf ships against.
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const ZOOM_MIN = 0.5;
const ZOOM_MAX = 2.5;
const ZOOM_STEP = 0.15;

export function PDFViewer({ url }: { url: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1.0);
  const [pageWidth, setPageWidth] = useState<number | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Measure container width so the page fits-to-width by default
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0;
      // Subtract horizontal padding/scroll allowance
      setPageWidth(Math.max(400, w - 64));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const goPrev = () => setPage((p) => Math.max(1, p - 1));
  const goNext = () => setPage((p) => (numPages ? Math.min(numPages, p + 1) : p));
  const zoomIn = () => setZoom((z) => Math.min(ZOOM_MAX, +(z + ZOOM_STEP).toFixed(2)));
  const zoomOut = () => setZoom((z) => Math.max(ZOOM_MIN, +(z - ZOOM_STEP).toFixed(2)));
  const resetZoom = () => setZoom(1.0);

  return (
    <div className="flex h-full flex-col bg-surface-1">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-border-subtle bg-surface-2 px-4 py-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={goPrev}
            disabled={page <= 1}
            className="rounded-sm border border-border-default bg-surface-1 px-2 py-1 font-mono text-xs text-secondary hover:border-border-strong hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Previous page"
          >
            ← Prev
          </button>
          <div className="font-mono text-xs text-tertiary">
            <input
              type="number"
              min={1}
              max={numPages ?? 1}
              value={page}
              onChange={(e) => {
                const n = Number(e.target.value);
                if (Number.isFinite(n) && numPages) {
                  setPage(Math.max(1, Math.min(numPages, n)));
                }
              }}
              className="w-12 rounded-sm border border-border-default bg-surface-1 px-1.5 py-1 text-center text-xs text-primary focus:border-accent focus:outline-none"
              aria-label="Page number"
            />
            <span className="mx-1.5">/</span>
            <span>{numPages ?? "—"}</span>
          </div>
          <button
            type="button"
            onClick={goNext}
            disabled={!numPages || page >= numPages}
            className="rounded-sm border border-border-default bg-surface-1 px-2 py-1 font-mono text-xs text-secondary hover:border-border-strong hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Next page"
          >
            Next →
          </button>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={zoomOut}
            disabled={zoom <= ZOOM_MIN}
            className="rounded-sm border border-border-default bg-surface-1 px-2 py-1 font-mono text-xs text-secondary hover:border-border-strong hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Zoom out"
          >
            −
          </button>
          <button
            type="button"
            onClick={resetZoom}
            className="rounded-sm px-2 py-1 font-mono text-xs text-tertiary hover:text-accent transition-colors"
            aria-label="Reset zoom"
          >
            {Math.round(zoom * 100)}%
          </button>
          <button
            type="button"
            onClick={zoomIn}
            disabled={zoom >= ZOOM_MAX}
            className="rounded-sm border border-border-default bg-surface-1 px-2 py-1 font-mono text-xs text-secondary hover:border-border-strong hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Zoom in"
          >
            +
          </button>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-3 rounded-sm border border-border-default bg-surface-1 px-2 py-1 font-mono text-xs text-secondary hover:border-border-strong hover:text-primary"
            title="Open the source PDF in a new tab"
          >
            Open ↗
          </a>
        </div>
      </div>

      {/* Page area */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto bg-surface-1 px-8 py-6"
      >
        {loadError ? (
          <div className="mx-auto max-w-md border border-critical/40 bg-critical-muted rounded-sm p-6">
            <div className="font-mono text-[10px] uppercase tracking-wider text-critical mb-2">
              PDF failed to load
            </div>
            <p className="text-sm text-secondary">{loadError}</p>
          </div>
        ) : (
          <Document
            file={url}
            onLoadSuccess={({ numPages }) => {
              setNumPages(numPages);
              setLoadError(null);
            }}
            onLoadError={(err) => setLoadError(err.message)}
            loading={
              <div className="flex h-full items-center justify-center font-mono text-[10px] uppercase tracking-[0.2em] text-tertiary">
                Loading PDF…
              </div>
            }
            error={
              <div className="font-mono text-xs text-critical">
                Could not load PDF.
              </div>
            }
          >
            {pageWidth && numPages && (
              <Page
                pageNumber={page}
                width={pageWidth * zoom}
                renderAnnotationLayer
                renderTextLayer
                className="mx-auto shadow-2"
                loading={
                  <div className="mx-auto h-[800px] w-full max-w-3xl border border-border-subtle bg-surface-2 rounded-sm flex items-center justify-center font-mono text-[10px] uppercase tracking-[0.2em] text-tertiary">
                    Rendering page {page}…
                  </div>
                }
              />
            )}
          </Document>
        )}
      </div>
    </div>
  );
}
