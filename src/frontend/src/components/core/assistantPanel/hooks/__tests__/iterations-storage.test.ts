import {
  DEFAULT_ITERATIONS_LIMIT,
  MAX_ITERATIONS_LIMIT,
  parseIterationsCommand,
} from "../iterations-storage";

describe("parseIterationsCommand", () => {
  it("returns null for non-/iterations input", () => {
    expect(parseIterationsCommand("run the flow", null)).toBeNull();
    expect(parseIterationsCommand("/iterationsx", null)).toBeNull();
  });

  it("sets a numeric budget", () => {
    const r = parseIterationsCommand("/iterations 60", null);
    expect(r).toEqual(expect.objectContaining({ limit: 60, changed: true }));
  });

  it("resets with off/default/reset", () => {
    for (const w of ["off", "default", "reset"]) {
      const r = parseIterationsCommand(`/iterations ${w}`, 60);
      expect(r).toEqual(expect.objectContaining({ limit: null, changed: true }));
    }
  });

  it("reports current value without changing it", () => {
    const r = parseIterationsCommand("/iterations", 45);
    expect(r?.changed).toBe(false);
    expect(r?.limit).toBe(45);
    expect(r?.announcement).toContain("45");
  });

  it("mentions the default when unset", () => {
    const r = parseIterationsCommand("/iterations", null);
    expect(r?.announcement).toContain(String(DEFAULT_ITERATIONS_LIMIT));
  });

  it("rejects invalid or out-of-range numbers without changing", () => {
    for (const bad of ["abc", "0", "-1", String(MAX_ITERATIONS_LIMIT + 1)]) {
      const r = parseIterationsCommand(`/iterations ${bad}`, 30);
      expect(r?.changed).toBe(false);
      expect(r?.limit).toBe(30);
      expect(r?.announcement).toMatch(/invalid/i);
    }
  });
});
