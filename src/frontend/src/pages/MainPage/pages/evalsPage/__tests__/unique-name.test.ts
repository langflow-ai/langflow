import { datasetNameFromFile, uniqueName } from "../utils/unique-name";

describe("uniqueName", () => {
  it("should keep the base when no dataset uses it", () => {
    expect(uniqueName("Untitled dataset", ["Other"])).toBe("Untitled dataset");
  });

  it("should add the first free number when the base is taken", () => {
    expect(
      uniqueName("Untitled dataset", [
        "untitled dataset",
        "Untitled dataset 2",
      ]),
    ).toBe("Untitled dataset 3");
  });

  it("should stay within the name length limit", () => {
    const base = "x".repeat(255);
    const next = uniqueName(base, [base]);
    expect(next).toHaveLength(255);
    expect(next.endsWith(" 2")).toBe(true);
  });
});

describe("datasetNameFromFile", () => {
  it("should drop the extension", () => {
    expect(datasetNameFromFile("support-qa.v2.csv")).toBe("support-qa.v2");
  });

  it("should keep a name that is only an extension", () => {
    expect(datasetNameFromFile(".csv")).toBe(".csv");
  });
});
