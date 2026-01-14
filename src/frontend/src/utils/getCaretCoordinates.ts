/**
 * Caret coordinate utilities for positioning autocomplete dropdowns.
 *
 * Uses a "mirror div" technique to calculate the pixel position of the caret
 * within a textarea or input element. This works by creating a hidden div with
 * the same styling as the input, copying the text up to the caret position,
 * and measuring where the text ends.
 *
 * @module getCaretCoordinates
 */

/** CSS properties to copy from the source element to the mirror div */
const properties = [
  "direction",
  "boxSizing",
  "width",
  "height",
  "overflowX",
  "overflowY",
  "borderTopWidth",
  "borderRightWidth",
  "borderBottomWidth",
  "borderLeftWidth",
  "borderStyle",
  "paddingTop",
  "paddingRight",
  "paddingBottom",
  "paddingLeft",
  "fontStyle",
  "fontVariant",
  "fontWeight",
  "fontStretch",
  "fontSize",
  "fontSizeAdjust",
  "lineHeight",
  "fontFamily",
  "textAlign",
  "textTransform",
  "textIndent",
  "textDecoration",
  "letterSpacing",
  "wordSpacing",
  "tabSize",
  "MozTabSize",
] as const;

const isBrowser = typeof window !== "undefined";

/**
 * Coordinates returned by getCaretCoordinates.
 */
export interface CaretCoordinates {
  /** Distance from top of element to caret (in pixels) */
  top: number;
  /** Distance from left of element to caret (in pixels) */
  left: number;
  /** Line height at caret position (in pixels) */
  height: number;
}

/**
 * Calculate the pixel coordinates of the caret within a textarea or input.
 *
 * @param element - The textarea or input element
 * @param position - The character index position of the caret
 * @returns Coordinates relative to the element's content area
 *
 * @example
 * ```ts
 * const textarea = document.querySelector('textarea');
 * const pos = textarea.selectionStart;
 * const coords = getCaretCoordinates(textarea, pos);
 *
 * // Position dropdown at caret
 * dropdown.style.top = `${coords.top + coords.height}px`;
 * dropdown.style.left = `${coords.left}px`;
 * ```
 */
export function getCaretCoordinates(
  element: HTMLTextAreaElement | HTMLInputElement,
  position: number,
): CaretCoordinates {
  if (!isBrowser) {
    return { top: 0, left: 0, height: 0 };
  }

  const div = document.createElement("div");
  div.id = "input-textarea-caret-position-mirror-div";
  document.body.appendChild(div);

  const style = div.style;
  const computed = window.getComputedStyle(element);
  const isInput = element.nodeName === "INPUT";

  // Default textarea styles
  style.whiteSpace = isInput ? "nowrap" : "pre-wrap";
  style.wordWrap = "break-word";

  // Position off-screen
  style.position = "absolute";
  style.visibility = "hidden";

  // Transfer the element's properties to the div
  for (const prop of properties) {
    if (isInput && prop === "lineHeight") {
      // Special case for <input>s because text is rendered centered
      if (computed.boxSizing === "border-box") {
        const height = parseInt(computed.height);
        const outerHeight =
          parseInt(computed.paddingTop) +
          parseInt(computed.paddingBottom) +
          parseInt(computed.borderTopWidth) +
          parseInt(computed.borderBottomWidth);
        const targetHeight = outerHeight + parseInt(computed.lineHeight);
        if (height > targetHeight) {
          style.lineHeight = height - outerHeight + "px";
        } else if (height === targetHeight) {
          style.lineHeight = computed.lineHeight;
        } else {
          style.lineHeight = "0";
        }
      } else {
        style.lineHeight = computed.height;
      }
    } else {
      style[prop as any] = computed[prop as any];
    }
  }

  if (!isInput) {
    // For textareas, set overflow to auto to mimic scrolling
    style.overflow = "hidden";
  }

  const value = element.value;
  div.textContent = value.substring(0, position);

  if (isInput) {
    div.textContent = div.textContent.replace(/\s/g, "\u00a0");
  }

  const span = document.createElement("span");
  // Use zero-width space so the span has height even if empty
  span.textContent = value.substring(position) || "\u200b";
  div.appendChild(span);

  const coordinates: CaretCoordinates = {
    top: span.offsetTop + parseInt(computed.borderTopWidth),
    left: span.offsetLeft + parseInt(computed.borderLeftWidth),
    height: parseInt(computed.lineHeight) || parseInt(computed.fontSize),
  };

  document.body.removeChild(div);

  return coordinates;
}
