"use client";

import { Fragment } from "react";

import type { Citation } from "@/lib/api";

import { CitationPill } from "./citation-pill";

interface MessageProps {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[] | null;
  /** True while the assistant message is still streaming. */
  streaming?: boolean;
}

/**
 * Render assistant content with [CIT-N] markers replaced by inline pills.
 * For user messages, just render plain text.
 */
function renderAssistantContent(content: string, citations: Citation[] | null | undefined) {
  if (!content) return null;
  const byId = new Map((citations ?? []).map((c) => [c.cit_id, c]));
  const regex = /\[CIT-(\d+)\]/g;

  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push(
        <Fragment key={key++}>{content.slice(lastIndex, match.index)}</Fragment>,
      );
    }
    const id = Number(match[1]);
    const cite = byId.get(id);
    if (cite) {
      parts.push(<CitationPill key={key++} citation={cite} />);
    } else {
      // Unresolved citation marker — keep the literal so it's debuggable
      parts.push(
        <span
          key={key++}
          className="font-mono text-[10px] text-tertiary"
          title="Citation not resolved"
        >
          {match[0]}
        </span>,
      );
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < content.length) {
    parts.push(<Fragment key={key++}>{content.slice(lastIndex)}</Fragment>);
  }
  return parts;
}

export function ChatMessage({ role, content, citations, streaming }: MessageProps) {
  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-sm bg-surface-3 border border-border-default px-3 py-2 text-sm text-primary leading-[1.55]">
          {content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] text-sm text-primary leading-[1.6]">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-accent mb-1.5">
          Assistant
        </div>
        <div className="break-words">
          {renderAssistantContent(content, citations)}
          {streaming && (
            <span
              className="inline-block ml-0.5 align-baseline h-3 w-2 bg-accent"
              style={{ animation: "blink 1s steps(2, end) infinite" }}
              aria-hidden
            />
          )}
        </div>
        <style jsx>{`
          @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
          }
        `}</style>
      </div>
    </div>
  );
}
