import enTranslations from "@/locales/en.json";

describe("GenericErrorComponent translation keys", () => {
  const keysUsed = [
    "misc.fetchError",
    "misc.fetchErrorDesc",
    "misc.timeoutError",
    "misc.timeoutErrorDesc",
  ] as const;

  it.each(keysUsed)("'%s' is defined in en.json", (key) => {
    expect((enTranslations as Record<string, string>)[key]).toBeDefined();
    expect((enTranslations as Record<string, string>)[key]).not.toBe("");
  });
});
