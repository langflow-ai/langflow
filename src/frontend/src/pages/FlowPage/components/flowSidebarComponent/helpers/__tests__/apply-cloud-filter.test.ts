import type { APIDataType } from "@/types/api";
import { applyCloudFilter } from "../apply-cloud-filter";

describe("applyCloudFilter", () => {
  it("should remove components where cloud_compatible is false", () => {
    const data: APIDataType = {
      models: {
        OpenAI: {
          description: "OpenAI",
          template: {},
          display_name: "OpenAI",
          documentation: "",
          cloud_compatible: true,
        } as any,
        Ollama: {
          description: "Ollama",
          template: {},
          display_name: "Ollama",
          documentation: "",
          cloud_compatible: false,
        } as any,
      },
    };

    const result = applyCloudFilter(data);
    expect(Object.keys(result.models)).toEqual(["OpenAI"]);
  });

  it("should keep components without cloud_compatible field (defaults to compatible)", () => {
    const data: APIDataType = {
      utilities: {
        TextSplitter: {
          description: "Splits text",
          template: {},
          display_name: "Text Splitter",
          documentation: "",
        } as any,
      },
    };

    const result = applyCloudFilter(data);
    expect(Object.keys(result.utilities)).toEqual(["TextSplitter"]);
  });

  it("should keep components where cloud_compatible is true", () => {
    const data: APIDataType = {
      models: {
        Anthropic: {
          description: "Anthropic",
          template: {},
          display_name: "Anthropic",
          documentation: "",
          cloud_compatible: true,
        } as any,
      },
    };

    const result = applyCloudFilter(data);
    expect(Object.keys(result.models)).toEqual(["Anthropic"]);
  });

  it("should handle empty categories", () => {
    const data: APIDataType = {
      empty_category: {},
    };

    const result = applyCloudFilter(data);
    expect(result.empty_category).toEqual({});
  });

  it("should handle multiple categories with mixed compatibility", () => {
    const data: APIDataType = {
      models: {
        OpenAI: {
          description: "OpenAI",
          template: {},
          display_name: "OpenAI",
          documentation: "",
          cloud_compatible: true,
        } as any,
        Ollama: {
          description: "Ollama",
          template: {},
          display_name: "Ollama",
          documentation: "",
          cloud_compatible: false,
        } as any,
      },
      vectorstores: {
        Pinecone: {
          description: "Pinecone",
          template: {},
          display_name: "Pinecone",
          documentation: "",
        } as any,
        FAISS: {
          description: "FAISS",
          template: {},
          display_name: "FAISS",
          documentation: "",
          cloud_compatible: false,
        } as any,
      },
    };

    const result = applyCloudFilter(data);
    expect(Object.keys(result.models)).toEqual(["OpenAI"]);
    expect(Object.keys(result.vectorstores)).toEqual(["Pinecone"]);
  });

  it("should not mutate the original data", () => {
    const data: APIDataType = {
      models: {
        Ollama: {
          description: "Ollama",
          template: {},
          display_name: "Ollama",
          documentation: "",
          cloud_compatible: false,
        } as any,
      },
    };

    applyCloudFilter(data);
    expect(Object.keys(data.models)).toEqual(["Ollama"]);
  });
});
