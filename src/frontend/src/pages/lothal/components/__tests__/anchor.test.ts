import { decodeElementId, resolveAnchor } from "../d2/anchor";

// Build a D2-shaped DOM: a root with element groups whose class carries the
// base64-encoded id D2 bakes in, mirroring the real rendered SVG.
const b64 = (s: string) => window.btoa(s);

function group(id: string, klass: string, ...children: Element[]): HTMLElement {
  const el = document.createElement("div");
  el.className = `${klass} ${b64(id)}`;
  children.forEach((c) => el.appendChild(c));
  return el;
}

function text(content: string): HTMLElement {
  const t = document.createElement("text");
  t.textContent = content;
  return t;
}

describe("decodeElementId", () => {
  it("decodes a base64 id and rejects non-base64 classes", () => {
    expect(decodeElementId(b64("user"))).toBe("user");
    // "shape" is not valid base64 (length not a multiple of 4) → null.
    expect(decodeElementId("shape")).toBeNull();
  });

  it("decodes multi-byte UTF-8 ids", () => {
    // D2 bakes ids in as base64 of their UTF-8 bytes; "café" has a two-byte char,
    // which exercises the TextDecoder path (the old escape() idiom this replaced).
    const b64Utf8 = window.btoa(
      String.fromCharCode(...Array.from(new TextEncoder().encode("café"))),
    );
    expect(decodeElementId(b64Utf8)).toBe("café");
  });

  it("rejects base64 that decodes to invalid UTF-8 (fatal mode) → null", () => {
    // 0xFF is never a valid UTF-8 lead byte; `fatal: true` must throw → null,
    // so an arbitrary base64-shaped class is never mistaken for a real D2 id.
    const invalidUtf8 = window.btoa(String.fromCharCode(0xff, 0xfe));
    expect(decodeElementId(invalidUtf8)).toBeNull();
  });
});

describe("resolveAnchor", () => {
  it("resolves a clicked node to its id and label", () => {
    const root = document.createElement("div");
    const node = group("checkout", "shape");
    root.appendChild(node);
    const a = resolveAnchor(node, root);
    expect(a).toEqual({ kind: "node", id: "checkout", label: "checkout" });
  });

  it("resolves duplicate-label nodes to distinct ids", () => {
    const root = document.createElement("div");
    const n1 = group("user", "shape");
    const n2 = group("user2", "shape");
    root.append(n1, n2);
    expect(resolveAnchor(n1, root)?.id).toBe("user");
    expect(resolveAnchor(n2, root)?.id).toBe("user2");
  });

  it("anchors a sequence message by its label, not the src→dst relation", () => {
    const root = document.createElement("div");
    const edge = group("(api -> db)[0]", "connection", text("POST /sync"));
    root.appendChild(edge);
    const a = resolveAnchor(edge, root);
    expect(a).toMatchObject({
      kind: "edge",
      id: "api → db",
      label: "POST /sync",
      src: "api",
      dst: "db",
      index: 0,
    });
  });

  it("disambiguates parallel edges with #index", () => {
    const root = document.createElement("div");
    const e0 = group("(a -> b)[0]", "connection", text("first"));
    const e1 = group("(a -> b)[1]", "connection", text("second"));
    root.append(e0, e1);
    expect(resolveAnchor(e0, root)?.id).toBe("a → b");
    expect(resolveAnchor(e1, root)).toMatchObject({
      id: "a → b #2",
      index: 1,
    });
  });

  it("prefers an enclosing edge over a node when both are on the path", () => {
    const root = document.createElement("div");
    const label = group("api", "shape");
    const edge = group("(api -> db)[0]", "connection", label);
    root.appendChild(edge);
    expect(resolveAnchor(label, root)?.kind).toBe("edge");
  });

  it("returns null when the click misses every diagram element", () => {
    const root = document.createElement("div");
    const blank = document.createElement("div");
    root.appendChild(blank);
    expect(resolveAnchor(blank, root)).toBeNull();
  });
});
