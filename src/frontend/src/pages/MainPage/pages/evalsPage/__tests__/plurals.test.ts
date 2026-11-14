import i18n from "@/i18n";

describe("evals plural strings", () => {
  it("should use the singular for one row and the plural otherwise", () => {
    expect(i18n.t("evals.csv.imported", { count: 1, lng: "en" })).toBe(
      "1 row imported",
    );
    expect(i18n.t("evals.csv.imported", { count: 3, lng: "en" })).toBe(
      "3 rows imported",
    );
    expect(i18n.t("evals.estimate.calls", { count: 1, lng: "en" })).toBe(
      "1 call",
    );
  });
});
