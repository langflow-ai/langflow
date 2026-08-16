import { useTranslation } from "react-i18next";

// Light markdown-to-speech pass, not a parser: drops the syntax characters a
// screen reader would otherwise read aloud ("asterisk asterisk bold") while
// keeping the content, including inside code fences.
export function stripMarkdownForSpeech(text: string): string {
  return text
    .replace(/```[a-zA-Z0-9-]*\n?/g, " ")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/(\*{1,3}|_{1,3})([^*_]+)\1/g, "$2")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*>\s?/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}

// Screen-reader-only companion to useResponseCompleteCue: announces the
// completed reply's text once streaming settles (the transcript itself is a
// muted role="log", so this region is the reply's only path to the screen
// reader).
export function ResponseCompleteStatus({
  completedCount,
  completedText = "",
  isAnnouncing = true,
}: {
  completedCount: number;
  completedText?: string;
  // False once the cue has retired the announcement, which empties the region
  // back to its initial state: the same "" -> text transition the first
  // announcement already relies on, so nothing is lost on the next reply.
  isAnnouncing?: boolean;
}) {
  const { t } = useTranslation();
  const spoken =
    stripMarkdownForSpeech(completedText) || t("chat.responseComplete");
  // A single persistent text node that mutates in place is the announcement
  // pattern WebKit's live-region diffing handles reliably; remounting a keyed
  // child (remove + re-add of identical text) is dropped by Safari/VoiceOver
  // (LE-2041 QA). Alternate a trailing no-break space so identical
  // consecutive replies still produce a text change to announce.
  const message =
    completedCount > 0 && isAnnouncing
      ? spoken + (completedCount % 2 === 0 ? "\u00a0" : "")
      : "";
  return (
    <div role="status" aria-live="polite" className="sr-only">
      {message}
    </div>
  );
}
