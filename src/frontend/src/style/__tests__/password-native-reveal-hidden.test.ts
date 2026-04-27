import { readFileSync } from "node:fs";
import path from "node:path";

/**
 * Regression guard for the duplicate password reveal icon bug reported on
 * Windows (Edge/WebView2-based browsers). The browser engine injects a native
 * password reveal control via the ::-ms-reveal pseudo-element. Without an
 * explicit CSS rule hiding it, the native control overlaps Langflow's own
 * Eye/EyeOff button rendered in InputComponent, producing two visible eye
 * icons on the login screen when AUTO_LOGIN=false.
 *
 * Fix lives in src/style/applies.css as a top-level CSS rule (intentionally
 * OUTSIDE any @layer so Tailwind/PostCSS cannot reorder or deprioritize it).
 */
describe("password field - native Edge/WebView2 reveal icon", () => {
  const appliesCssPath = path.resolve(__dirname, "..", "applies.css");
  const cssSource = readFileSync(appliesCssPath, "utf8");
  const normalized = cssSource.replace(/\s+/g, " ");

  it("should_hide_native_ms_reveal_pseudo_element_for_password_inputs", () => {
    expect(normalized).toMatch(/input\[type="password"\]::-ms-reveal/);
    expect(normalized).toMatch(
      /input\[type="password"\]::-ms-reveal[^{}]*,[^{}]*input\[type="password"\]::-ms-clear\s*\{[^}]*display:\s*none\s*!important/,
    );
  });

  it("should_hide_native_ms_clear_pseudo_element_for_password_inputs", () => {
    expect(normalized).toMatch(/input\[type="password"\]::-ms-clear/);
  });

  it("should_place_ms_reveal_rule_outside_tailwind_layers", () => {
    const lines = cssSource.split("\n");
    const ruleLineIndex = lines.findIndex((line) =>
      line.includes('input[type="password"]::-ms-reveal'),
    );
    expect(ruleLineIndex).toBeGreaterThan(-1);

    let openLayers = 0;
    for (let i = 0; i < ruleLineIndex; i++) {
      const line = lines[i];
      if (/@layer\s+\w+\s*\{/.test(line)) {
        openLayers++;
      } else if (/^\s*\}\s*$/.test(line) && openLayers > 0) {
        openLayers--;
      }
    }
    expect(openLayers).toBe(0);
  });
});
