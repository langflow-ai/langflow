import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * WCAG 2.2 SC 1.4.11 Non-text Contrast (LE-2270).
 *
 * The boundary that identifies an interactive control must reach 3:1 against
 * the adjacent background. That boundary comes from --control-boundary, so
 * this guard reads the real token values out of style/index.css and re-derives
 * the ratios. If someone lightens the token back toward --border, this fails.
 *
 * Jest mocks CSS imports (jest.config.js moduleNameMapper), so the stylesheet
 * is parsed from disk rather than read off a rendered element.
 */

const WCAG_NON_TEXT = 3;

const css = readFileSync(join(__dirname, "..", "index.css"), "utf8");

/** Grab a `--token: <h> <s>% <l>%;` triplet from the :root or .dark block. */
function readToken(theme: "root" | "dark", name: string) {
  // `:root {` runs to the `.dark {` that follows it; `.dark {` runs to EOF.
  const rootStart = css.indexOf(":root {");
  const darkStart = css.indexOf(".dark {");
  const block =
    theme === "root" ? css.slice(rootStart, darkStart) : css.slice(darkStart);
  const match = block.match(
    new RegExp(`--${name}:\\s*([\\d.]+)\\s+([\\d.]+)%\\s+([\\d.]+)%`),
  );
  if (!match) throw new Error(`--${name} not found in ${theme} block`);
  return [+match[1], +match[2], +match[3]] as const;
}

function hslToRgb([h, s, l]: readonly [number, number, number]) {
  const sat = s / 100;
  const lig = l / 100;
  const k = (n: number) => (n + h / 30) % 12;
  const a = sat * Math.min(lig, 1 - lig);
  const f = (n: number) =>
    lig - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return [f(0), f(8), f(4)].map((v) => Math.round(v * 255)) as [
    number,
    number,
    number,
  ];
}

function luminance([r, g, b]: [number, number, number]) {
  const f = (v: number) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

function contrast(
  a: readonly [number, number, number],
  b: readonly [number, number, number],
) {
  const [hi, lo] = [luminance(hslToRgb(a)), luminance(hslToRgb(b))].sort(
    (x, y) => y - x,
  );
  return (hi + 0.05) / (lo + 0.05);
}

describe("WCAG 1.4.11 — control boundary contrast", () => {
  // The surfaces a bordered control actually sits on, per theme.
  const surfaces = ["background", "muted", "canvas"] as const;

  describe.each(["root", "dark"] as const)("%s theme", (theme) => {
    const boundary = readToken(theme, "control-boundary");

    it.each(surfaces)(
      `--control-boundary reaches ${WCAG_NON_TEXT}:1 on --%s`,
      (surface) => {
        const ratio = contrast(boundary, readToken(theme, surface));
        expect(ratio).toBeGreaterThanOrEqual(WCAG_NON_TEXT);
      },
    );
  });

  it("documents the deliberate split without failing future --border improvements", () => {
    // --border paints dividers, card edges and table rules, which SC 1.4.11
    // does not cover, so it is NOT held to the 3:1 threshold. No upper-bound
    // assertion: if a future change makes --border compliant on its own,
    // that is a valid improvement (and --control-boundary could be retired),
    // not a failure. This case only pins that the token still parses.
    expect(readToken("root", "border")).toHaveLength(3);
  });
});
