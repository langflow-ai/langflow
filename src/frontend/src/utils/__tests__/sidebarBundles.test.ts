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

  it("classifies Serping API as a sidebar bundle", () => {
    expect(SIDEBAR_BUNDLES).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          display_name: "Serping API",
          icon: "Search",
          name: "serpingapi",
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

  it("classifies Microsoft 365 as a sidebar bundle", () => {
    expect(SIDEBAR_BUNDLES).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          display_name: "Microsoft 365",
          icon: "Microsoft",
          name: "microsoft",
        }),
      ]),
    );
  });

  it("keeps the Microsoft 365 group separate from Azure", () => {
    const names = SIDEBAR_BUNDLES.map((bundle) => bundle.name);
    expect(names).toContain("azure");
    expect(names).toContain("microsoft");
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

  it("classifies Slack as a sidebar bundle", () => {
    expect(SIDEBAR_BUNDLES).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          display_name: "Slack",
          icon: "Slack",
          name: "slack",
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
