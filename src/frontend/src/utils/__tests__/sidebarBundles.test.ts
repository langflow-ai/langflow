import { SIDEBAR_BUNDLES } from "../styleUtils";

describe("SIDEBAR_BUNDLES", () => {
  it("classifies AnonRouter as a sidebar bundle", () => {
    expect(SIDEBAR_BUNDLES).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          display_name: "AnonRouter",
          icon: "AnonRouter",
          name: "anonrouter",
        }),
      ]),
    );
  });

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

  it("classifies Serply as a sidebar bundle", () => {
    expect(SIDEBAR_BUNDLES).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          display_name: "Serply",
          icon: "Search",
          name: "serply",
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

  it("classifies Figranium as a sidebar bundle", () => {
    expect(SIDEBAR_BUNDLES).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          display_name: "Figranium",
          icon: "Figranium",
          name: "figranium",
        }),
      ]),
    );
  });
});
