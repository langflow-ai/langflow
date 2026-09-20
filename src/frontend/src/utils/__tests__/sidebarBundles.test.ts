import { SIDEBAR_BUNDLES } from "../styleUtils";

describe("SIDEBAR_BUNDLES", () => {
  it("classifies PaddleOCR as a sidebar bundle", () => {
    expect(SIDEBAR_BUNDLES).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          display_name: "PaddleOCR",
          icon: "FileSearch",
          name: "paddle",
        }),
      ]),
    );
  });

  it("classifies IBM Confluent as a sidebar bundle", () => {
    expect(SIDEBAR_BUNDLES).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          display_name: "IBM Confluent",
          icon: "Confluent",
          name: "confluent",
        }),
      ]),
    );
  });

  it("classifies ToolGuard as a sidebar bundle", () => {
    expect(SIDEBAR_BUNDLES).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          display_name: "ToolGuard",
          icon: "ShieldCheck",
          name: "toolguard",
        }),
      ]),
    );
  });
});
