import i18n, { loadLanguage } from "../i18n";

describe("loadLanguage", () => {
  beforeEach(() => {
    // Remove any bundles added by previous tests so each test starts clean.
    jest.resetModules();
  });

  it("resolves without throwing for an unknown locale", async () => {
    await expect(loadLanguage("xx")).resolves.toBeUndefined();
  });

  it("does not register a bundle for an unknown locale", async () => {
    await loadLanguage("xx");
    expect(i18n.hasResourceBundle("xx", "translation")).toBe(false);
  });

  it("returns early without throwing for 'en'", async () => {
    await expect(loadLanguage("en")).resolves.toBeUndefined();
  });
});
