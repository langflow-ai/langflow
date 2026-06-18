// The three regression cases the D.7 ticket calls out for click-to-anchor
// resolution (lifted from the browser-verified spike): duplicate-label nodes
// resolve to distinct ids, parallel edges disambiguate via `#index`, and a
// sequence message anchors by its message label — not the src→dst relation.

import { resolveAnchor } from "../anchor";

// D2 bakes each element's source id into the SVG as a base64 CSS class.
const b64 = (s: string) => window.btoa(s);

function leaf(tag: string): HTMLElement {
  return document.createElement(tag);
}

/** A D2-style group (`shape`/`connection` + base64 id class) with a child. */
function group(role: string, id: string, child: HTMLElement): HTMLElement {
  const g = document.createElement("g");
  g.setAttribute("class", `${role} ${b64(id)}`);
  g.appendChild(child);
  return g;
}

describe("resolveAnchor regression cases", () => {
  it("resolves duplicate-label nodes to distinct ids", () => {
    const root = document.createElement("svg");
    // Two nodes that DISPLAY the same label but carry different D2 ids.
    const text1 = leaf("text");
    text1.textContent = "Database";
    const text2 = leaf("text");
    text2.textContent = "Database";
    const n1 = group("shape", "db1", text1);
    const n2 = group("shape", "db2", text2);
    root.append(n1, n2);

    const a1 = resolveAnchor(text1, root);
    const a2 = resolveAnchor(text2, root);
    expect(a1).toMatchObject({ kind: "node", id: "db1" });
    expect(a2).toMatchObject({ kind: "node", id: "db2" });
    expect(a1?.id).not.toBe(a2?.id);
  });

  it("disambiguates parallel edges with #index", () => {
    const root = document.createElement("svg");
    const t0 = leaf("text");
    t0.textContent = "save";
    const t1 = leaf("text");
    t1.textContent = "load";
    // D2 tags the second parallel connection with a [1] suffix.
    const e0 = group("connection", "user -> db", t0);
    const e1 = group("connection", "(user -> db)[1]", t1);
    root.append(e0, e1);

    const a0 = resolveAnchor(t0, root);
    const a1 = resolveAnchor(t1, root);
    expect(a0).toMatchObject({ kind: "edge", id: "user → db", index: 0 });
    expect(a1).toMatchObject({ kind: "edge", id: "user → db #2", index: 1 });
    expect(a0?.id).not.toBe(a1?.id);
  });

  it("anchors a sequence message by its label, not the node relation", () => {
    const root = document.createElement("svg");
    const msg = leaf("text");
    msg.textContent = "POST /sync";
    const conn = group("connection", "alice -> bob", msg);
    root.append(conn);

    const a = resolveAnchor(msg, root);
    expect(a).toMatchObject({
      kind: "edge",
      id: "alice → bob",
      label: "POST /sync",
      src: "alice",
      dst: "bob",
    });
  });
});
