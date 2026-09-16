import type { APIClassType, APIDataType } from "@/types/api";
import { applyFeatureFlagFilters } from "../apply-feature-flag-filters";

const component = (
  display_name: string,
  template: Record<string, unknown> = {},
): APIClassType =>
  ({ display_name, description: "", template }) as unknown as APIClassType;

const connectionField = (required: boolean) => ({
  type: "connection_ref",
  required,
  show: true,
  list: false,
  readonly: false,
  provider: "google",
});

const buildRawData = (): APIDataType => ({
  files_and_knowledge: {
    File: component("File"),
    KnowledgeBase: component("Knowledge Base"),
  },
  google: {
    GmailSendComponent: component("Gmail Send", {
      connection: connectionField(true),
    }),
    GmailLoaderComponent: component("Gmail Loader", {
      connection: connectionField(false),
    }),
  },
  microsoft: {
    OutlookSendComponent: component("Outlook Send", {
      connection: { ...connectionField(true), provider: "microsoft" },
    }),
  },
});

describe("applyFeatureFlagFilters", () => {
  it("returns the store data untouched when every feature is enabled", () => {
    const rawData = buildRawData();

    const result = applyFeatureFlagFilters(rawData, {
      enableKnowledgeBases: true,
      enableIntegrations: true,
    });

    expect(result).toBe(rawData);
  });

  describe("with ENABLE_INTEGRATIONS off", () => {
    const options = { enableKnowledgeBases: true, enableIntegrations: false };

    it("hides components that require a connection, whatever the provider", () => {
      const result = applyFeatureFlagFilters(buildRawData(), options);

      expect(Object.keys(result.google)).toEqual(["GmailLoaderComponent"]);
      expect(result.microsoft).toEqual({});
    });

    it("leaves other categories alone", () => {
      const rawData = buildRawData();

      const result = applyFeatureFlagFilters(rawData, options);

      expect(result.files_and_knowledge).toEqual(rawData.files_and_knowledge);
    });

    it("does not mutate the store data", () => {
      const rawData = buildRawData();
      const snapshot = JSON.parse(JSON.stringify(rawData));

      applyFeatureFlagFilters(rawData, options);

      expect(rawData).toEqual(snapshot);
    });
  });

  describe("with ENABLE_KNOWLEDGE_BASES off", () => {
    it("strips KnowledgeBase and keeps connection-backed components when integrations are on", () => {
      const rawData = buildRawData();

      const result = applyFeatureFlagFilters(rawData, {
        enableKnowledgeBases: false,
        enableIntegrations: true,
      });

      expect(Object.keys(result.files_and_knowledge)).toEqual(["File"]);
      expect(Object.keys(result.google)).toEqual([
        "GmailSendComponent",
        "GmailLoaderComponent",
      ]);
      expect(rawData.files_and_knowledge).toHaveProperty("KnowledgeBase");
    });

    it("applies both filters when both features are off", () => {
      const rawData = buildRawData();
      const snapshot = JSON.parse(JSON.stringify(rawData));

      const result = applyFeatureFlagFilters(rawData, {
        enableKnowledgeBases: false,
        enableIntegrations: false,
      });

      expect(Object.keys(result.files_and_knowledge)).toEqual(["File"]);
      expect(Object.keys(result.google)).toEqual(["GmailLoaderComponent"]);
      expect(result.microsoft).toEqual({});
      expect(rawData).toEqual(snapshot);
    });

    it("tolerates data without a files_and_knowledge category", () => {
      const result = applyFeatureFlagFilters(
        { google: {} },
        { enableKnowledgeBases: false, enableIntegrations: false },
      );

      expect(result).toEqual({ google: {} });
    });
  });
});
