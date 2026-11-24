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

const QUOTE = "'";

export interface FieldMentionMatch {
  /** Index of the opening quote of the already-inserted component token. */
  start: number;
  /** Component id captured from inside the quotes. */
  componentId: string;
  /** Text typed after the ``.`` (used to filter the field list). */
  query: string;
}

/**
 * Detect a field mention being typed right after a confirmed component token,
 * i.e. the caret sits inside ``'componentId'.fieldQuery``.
 *
 * The component token is quoted and space-free, so the ``.`` must be adjacent
 * to the closing quote — a whitespace or another quote in the field query
 * cancels the match so prose after a finished token never re-triggers.
 */
export function detectFieldMention(
  value: string,
  caret: number,
): FieldMentionMatch | null {
  let i = caret - 1;
  for (; i >= 0; i--) {
    const ch = value[i];
    if (ch === ".") break;
    if (WHITESPACE.test(ch) || ch === QUOTE) return null;
  }
  if (i < 0 || value[i] !== ".") return null;
  const dot = i;
  if (value[dot - 1] !== QUOTE) return null;
  const closeQuote = dot - 1;

  let open = -1;
  for (let j = closeQuote - 1; j >= 0; j--) {
    const ch = value[j];
    if (ch === QUOTE) {
      open = j;
      break;
    }
    if (WHITESPACE.test(ch)) return null;
  }
  if (open === -1) return null;

  const before = open > 0 ? value[open - 1] : "";
  if (before !== "" && !WHITESPACE.test(before)) return null;

  const componentId = value.slice(open + 1, closeQuote);
  if (!componentId) return null;
  return { start: open, componentId, query: value.slice(dot + 1, caret) };
}

/**
 * Wrap a component id in single quotes, Claude-Code style. No trailing space:
 * the caret lands right after the closing quote so typing ``.`` can chain into
 * a field mention (see {@link detectFieldMention}).
 */
export function formatMentionToken(componentId: string): string {
  return `'${componentId}'`;
}

/** Wrap a ``componentId.fieldName`` reference as a single quoted, terminal token. */
export function formatFieldMentionToken(
  componentId: string,
  fieldName: string,
): string {
  return `'${componentId}.${fieldName}' `;
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
