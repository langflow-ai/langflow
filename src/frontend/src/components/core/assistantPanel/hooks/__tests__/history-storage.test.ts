import { parseHistoryCommand } from "../history-storage";

describe("parseHistoryCommand", () => {
  it("returns null for non-/history input", () => {
    expect(parseHistoryCommand("build a flow", null)).toBeNull();
    expect(parseHistoryCommand("/historyx", null)).toBeNull();
  });

  it("sets a numeric limit", () => {
    const r = parseHistoryCommand("/history 10", null);
    expect(r).toEqual(expect.objectContaining({ limit: 10, changed: true }));
  });

  it("clears with off/all/clear", () => {
    for (const w of ["off", "all", "clear"]) {
      const r = parseHistoryCommand(`/history ${w}`, 5);
      expect(r).toEqual(
        expect.objectContaining({ limit: null, changed: true }),
      );
    }
  });

  it("reports current value without changing it", () => {
    const r = parseHistoryCommand("/history", 7);
    expect(r?.changed).toBe(false);
    expect(r?.limit).toBe(7);
    expect(r?.announcement).toContain("7");
  });

  it("rejects invalid numbers without changing", () => {
    for (const bad of ["abc", "-1", "999"]) {
      const r = parseHistoryCommand(`/history ${bad}`, 3);
      expect(r?.changed).toBe(false);
      expect(r?.limit).toBe(3);
      expect(r?.announcement).toMatch(/invalid/i);
    }
  });
});
