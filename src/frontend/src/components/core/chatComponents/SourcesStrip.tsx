import type { CitationContent } from "@/types/chat";

/** Returns the URL if its scheme is http(s), otherwise null. Guards against
 * `javascript:` / `data:` / `vbscript:` and other unsafe schemes that
 * React would otherwise pass through to a clickable anchor in production. */
function safeUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  try {
    const parsed = new URL(raw);
    return parsed.protocol === "http:" || parsed.protocol === "https:"
      ? raw
      : null;
  } catch {
    return null;
  }
}

/** Best-effort host extraction. Returns null for unparseable inputs so the
 * caller can decide whether to fall back to the raw URL or hide the chip. */
function extractDomain(raw: string | null | undefined): string | null {
  if (!raw) return null;
  try {
    const parsed = new URL(raw);
    return parsed.hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

function FaviconImg({ domain }: { domain: string }) {
  // Google's favicon service handles missing icons gracefully (returns a
  // globe), so we don't need to plumb our own onError state.
  const src = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=32`;
  return (
    <img
      src={src}
      alt=""
      width={16}
      height={16}
      className="rounded-sm flex-shrink-0"
      loading="lazy"
    />
  );
}

function SourceCard({ citation }: { citation: CitationContent }) {
  const url = safeUrl(citation.url);
  const domain = extractDomain(citation.url) ?? "source";
  const heading = citation.title || domain;
  const inner = (
    <div className="flex flex-col gap-1 p-3 w-56 flex-shrink-0 rounded-lg border border-border bg-background hover:bg-muted/50 transition-colors h-full">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <FaviconImg domain={domain} />
        <span className="truncate">{domain}</span>
      </div>
      <p className="text-sm font-medium line-clamp-2">{heading}</p>
      {citation.cited_text && (
        <p className="text-xs text-muted-foreground line-clamp-2 italic">
          {citation.cited_text}
        </p>
      )}
    </div>
  );
  if (!url) {
    // URL was missing or unsafe — render the card content as a div so
    // there's no clickable surface routing to a javascript: handler.
    return inner;
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="no-underline text-foreground"
    >
      {inner}
    </a>
  );
}

/** Horizontally-scrolling row of source cards. Used both for single
 * citations and for coalesced groups of consecutive citations. */
export function SourcesStrip({ citations }: { citations: CitationContent[] }) {
  if (citations.length === 0) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {citations.length > 1 ? "Sources" : "Source"}
      </div>
      <div className="flex flex-row gap-2 overflow-x-auto pb-1">
        {citations.map((citation, idx) => (
          <SourceCard
            key={`${citation.id ?? citation.url ?? "src"}-${idx}`}
            citation={citation}
          />
        ))}
      </div>
    </div>
  );
}
