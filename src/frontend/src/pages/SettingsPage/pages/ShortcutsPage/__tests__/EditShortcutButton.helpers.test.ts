import {
  checkForKeys,
  findShortcutByName,
  getFixedCombination,
  isDuplicateCombination,
  normalizeRecordedCombination,
} from "../EditShortcutButton/helpers";

describe("EditShortcutButton helpers", () => {
  const shortcuts = [
    { name: "Docs", display_name: "Docs", shortcut: "mod+shift+d" },
    { name: "Code", display_name: "Code", shortcut: "mod+." },
    { name: "Open Playground", display_name: "Playground", shortcut: "mod+k" },
  ];

  it("finds a shortcut by name", () => {
    const result = findShortcutByName(shortcuts, "open playground");
    expect(result?.shortcut).toBe("mod+k");
  });

  it("detects duplicate combinations across shortcuts", () => {
    const hasDuplicate = isDuplicateCombination(shortcuts, "Code", "mod+k");
    expect(hasDuplicate).toBe(true);
  });

  it("returns false for duplicates on the same shortcut", () => {
    const hasDuplicate = isDuplicateCombination(
      shortcuts,
      "Open Playground",
      "mod+k",
    );
    expect(hasDuplicate).toBe(false);
  });

  it("normalizes recorded combinations", () => {
    expect(normalizeRecordedCombination("Ctrl + K")).toBe("mod+k");
    expect(normalizeRecordedCombination("Cmd + Shift + P")).toBe("mod+shift+p");
  });

  it("builds fixed combinations", () => {
    expect(getFixedCombination(null, "space")).toBe("Space");
    expect(getFixedCombination("Ctrl", "k")).toBe("Ctrl + K");
  });

  it("checks for existing keys", () => {
    expect(checkForKeys("Ctrl + K", "Ctrl")).toBe(true);
    expect(checkForKeys("Ctrl + K", "Shift")).toBe(false);
  });
});
