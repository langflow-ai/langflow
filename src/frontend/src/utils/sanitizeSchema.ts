import type { Schema } from "hast-util-sanitize";
import { defaultSchema } from "rehype-sanitize";

/**
 * Custom sanitization schema for markdown content
 * Based on GitHub's sanitization rules but optimized for performance
 *
 * Security: Blocks XSS vectors while allowing safe markdown/HTML elements
 * Performance: Uses allowlist approach with minimal processing overhead
 */
export const markdownSanitizeSchema: Schema = {
  ...(defaultSchema || {}),
  attributes: {
    ...(defaultSchema?.attributes || {}),
    // Allow common attributes for styling and structure
    "*": ["className", "id", ...(defaultSchema?.attributes?.["*"] || [])],
    // Allow safe link attributes
    a: ["href", "title", "target", "rel"],
    // Allow image attributes
    img: ["src", "alt", "title", "width", "height"],
    // Allow video attributes (safe subset)
    video: ["src", "controls", "width", "height", "poster"],
    // Allow audio attributes (safe subset)
    audio: ["src", "controls"],
    // Allow code block attributes
    code: ["className"],
    pre: ["className"],
    // Allow table attributes
    td: ["align", "colSpan", "rowSpan"],
    th: ["align", "colSpan", "rowSpan"],
  },
  // Remove dangerous protocols
  protocols: {
    href: ["http", "https", "mailto"],
    src: ["http", "https"], // Used by img, video, audio
  },
  // Strip dangerous tags completely
  strip: ["script", "style"],
  // Allow safe HTML tags for markdown rendering
  tagNames: [
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "br",
    "hr",
    "strong",
    "em",
    "u",
    "s",
    "del",
    "ins",
    "code",
    "pre",
    "a",
    "img",
    "video",
    "audio",
    "ul",
    "ol",
    "li",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "blockquote",
    "div",
    "span",
    "sup",
    "sub",
  ],
};
