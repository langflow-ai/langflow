/**
 * Pure helpers for the assistant input's "@-mention" of canvas components.
 * No React, no store access — kept isolated so the trigger detection and the
 * token substitution can be unit-tested directly.
 */

export interface MentionMatch {
  /** Index of the triggering ``@`` in the textarea value. */
  start: number;
  /** Text the user typed after ``@`` (used to filter the component list). */
  query: string;
}

const WHITESPACE = /\s/;

/**
 * Detect an active ``@`` mention immediately to the left of the caret.
 *
 * A mention is only active when the ``@`` sits at a word boundary (start of
 * input or after whitespace) and no whitespace separates it from the caret —
 * so an email like ``a@b`` or a finished token never re-triggers the popover.
 */
export function detectMention(
  value: string,
  caret: number,
): MentionMatch | null {
  for (let i = caret - 1; i >= 0; i--) {
    const ch = value[i];
    if (ch === "@") {
      const before = i > 0 ? value[i - 1] : "";
      if (before === "" || WHITESPACE.test(before)) {
        return { start: i, query: value.slice(i + 1, caret) };
      }
      return null;
    }
    if (WHITESPACE.test(ch)) return null;
  }
  return null;
}

/** Wrap a component id in single quotes, Claude-Code style, with a trailing space. */
export function formatMentionToken(componentId: string): string {
  return `'${componentId}' `;
}

export interface MentionReplacement {
  value: string;
  caret: number;
}

/** Replace the ``@query`` span (``start``..``caret``) with the quoted token. */
export function replaceMention(
  value: string,
  start: number,
  caret: number,
  token: string,
): MentionReplacement {
  const next = value.slice(0, start) + token + value.slice(caret);
  return { value: next, caret: start + token.length };
}
