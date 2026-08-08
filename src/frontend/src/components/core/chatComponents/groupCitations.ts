import type { CitationContent, ContentType } from "@/types/chat";

/** A run of flat content items: either a single non-citation item rendered
 * via ContentDisplay, or a coalesced run of citations rendered as one
 * SourcesStrip. The synthetic 'sources' kind exists so the renderer can
 * group consecutive citations into one Sources row without inventing a
 * fake content type or mutating the original list. */
export type FlatRun =
  | { kind: "single"; item: ContentType; index: number }
  | { kind: "sources"; citations: CitationContent[]; index: number };

/** Walk the flat items list and merge consecutive citation entries into
 * one 'sources' run. Non-citation items pass through as 'single' runs.
 * `index` is the position of the first contributing item, used as a
 * stable React key. */
export function groupConsecutiveCitations(items: ContentType[]): FlatRun[] {
  const runs: FlatRun[] = [];
  let i = 0;
  while (i < items.length) {
    const item = items[i];
    if (item.type !== "citation") {
      runs.push({ kind: "single", item, index: i });
      i += 1;
      continue;
    }
    const start = i;
    const citations: CitationContent[] = [];
    while (i < items.length && items[i].type === "citation") {
      citations.push(items[i] as CitationContent);
      i += 1;
    }
    runs.push({ kind: "sources", citations, index: start });
  }
  return runs;
}
