// The Lothal workspace chat composer (Epic D.7). A rich, contentEditable field:
// double-clicking a box or arrow on the D2 canvas drops an INLINE reference chip
// at the caret (the canvas double-click calls the imperative `insertAnchor`
// handle exposed here), so the user writes naturally — "change ▭user to a
// browser". On send each chip serializes back into the message as its exact,
// collision-safe D2 anchor id wrapped in backticks (`checkout`, `user -> db #2`),
// so the refinement engine (D.8) gets a precise handle on what the user means.
// Free text alone still works — chips are an accelerator, never a requirement.
//
// Lifted from the browser-verified spike (scratchpad/d2-reference/ProductView):
// the caret save/restore, chip insertion, and serialize loop are its contract.

import { forwardRef, useCallback, useImperativeHandle, useRef } from "react";
import type { Anchor } from "./d2/anchor";

export interface ChatComposerHandle {
  /** Insert an inline reference chip for `anchor` at the last caret position. */
  insertAnchor: (anchor: Anchor) => void;
  /** Move focus into the editor. */
  focus: () => void;
}

// A non-breaking space trails each chip so the caret has somewhere to land and
// the next keystroke isn't absorbed into the (uneditable) chip.
const NBSP = "\u00a0";

const chipGlyph = (kind: Anchor["kind"]) => (kind === "edge" ? "↔ " : "▭ ");

function SendGlyph({ size = 15 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M2.5 8h9M8 4.5 11.5 8 8 11.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export const ChatComposer = forwardRef<
  ChatComposerHandle,
  {
    onSend: (content: string) => void;
    /** Disables editing and the send affordance (e.g. while a reply is in flight). */
    disabled?: boolean;
    placeholder?: string;
  }
>(function ChatComposer(
  { onSend, disabled, placeholder = "Describe what you want to build…" },
  ref,
) {
  const editor = useRef<HTMLDivElement>(null);
  // The last caret position inside the editor, so a chip inserted by a canvas
  // double-click (which steals focus) lands where the user was typing.
  const savedRange = useRef<Range | null>(null);

  const saveCaret = useCallback(() => {
    const sel = window.getSelection();
    if (sel?.rangeCount && editor.current?.contains(sel.anchorNode)) {
      savedRange.current = sel.getRangeAt(0).cloneRange();
    }
  }, []);

  const insertAnchor = useCallback(
    (a: Anchor) => {
      const el = editor.current;
      // The field is non-editable while a reply is in flight; the canvas
      // onAnchor stays live, so guard against dropping a chip into it then.
      if (!el || disabled) return;

      const chip = document.createElement("span");
      chip.className = "lothal-chip";
      chip.contentEditable = "false";
      chip.dataset.id = a.id;
      chip.dataset.kind = a.kind;
      chip.textContent = chipGlyph(a.kind) + a.label;

      el.focus();
      // Restore the saved caret, or fall back to the end of the field (e.g. the
      // user never typed — they double-clicked an element first).
      let range = savedRange.current;
      if (!range || !el.contains(range.commonAncestorContainer)) {
        range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
      }
      range.insertNode(chip);
      const space = document.createTextNode(NBSP);
      range.setStartAfter(chip);
      range.insertNode(space);
      range.setStartAfter(space);
      range.collapse(true);
      const sel = window.getSelection();
      sel?.removeAllRanges();
      sel?.addRange(range);
      savedRange.current = range.cloneRange();
    },
    [disabled],
  );

  useImperativeHandle(
    ref,
    () => ({
      insertAnchor,
      focus: () => editor.current?.focus(),
    }),
    [insertAnchor],
  );

  // Serialize the editor: plain text verbatim, each chip as its exact D2 anchor
  // id in backticks. Walk the tree (not just top-level nodes) so chips nested in
  // a block survive as their id, and the structural breaks a contentEditable
  // makes for Shift+Enter (<br> / block containers) become newlines rather than
  // silently flattening. Returns "" when the field is effectively empty.
  const serialize = useCallback((): string => {
    const el = editor.current;
    if (!el) return "";
    const walk = (n: Node): string => {
      if (n.nodeType === Node.TEXT_NODE) {
        return (n.textContent ?? "").replace(/\u00a0/g, " ");
      }
      if (n.nodeType !== Node.ELEMENT_NODE) return "";
      const e = n as HTMLElement;
      if (e.dataset?.id) return `\`${e.dataset.id}\``;
      if (e.tagName === "BR") return "\n";
      let s = "";
      e.childNodes.forEach((c) => {
        s += walk(c);
      });
      // A block container ends a line; don't double up if it already did.
      if (["DIV", "P", "LI"].includes(e.tagName) && s && !s.endsWith("\n")) {
        s += "\n";
      }
      return s;
    };
    let out = "";
    el.childNodes.forEach((n) => {
      out += walk(n);
    });
    return out;
  }, []);

  const send = useCallback(() => {
    if (disabled) return;
    const content = serialize().trim();
    if (!content) return;
    onSend(content);
    if (editor.current) editor.current.innerHTML = "";
    savedRange.current = null;
  }, [disabled, onSend, serialize]);

  return (
    <div className="lothal-composer">
      <div className="lothal-composer-box">
        <div
          ref={editor}
          className="lothal-composer-editor"
          role="textbox"
          aria-label="Message"
          aria-multiline="true"
          data-placeholder={placeholder}
          contentEditable={!disabled}
          suppressContentEditableWarning
          onKeyUp={saveCaret}
          onMouseUp={saveCaret}
          onBlur={saveCaret}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button
          type="button"
          aria-label="Send"
          disabled={disabled}
          onClick={send}
          className="lothal-composer-send"
        >
          <SendGlyph />
        </button>
      </div>
      <p className="lothal-composer-hint mono">
        Enter to send · Shift+Enter for a new line · double-click a diagram
        element to reference it
      </p>
    </div>
  );
});
