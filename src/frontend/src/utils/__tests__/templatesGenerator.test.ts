import type { APIObjectType } from "@/types/api";
import { templatesGenerator } from "../reactflowUtils";

const asApiObject = (data: Record<string, unknown>) =>
  data as unknown as APIObjectType;

describe("templatesGenerator", () => {
  it("should create templates indexed by component key", () => {
    const data = asApiObject({
      models: {
        ChatInput: {
          template: { code: { value: "chat_code" } },
          display_name: "Chat Input",
        },
        ChatOutput: {
          template: { code: { value: "output_code" } },
          display_name: "Chat Output",
        },
      },
    });

    const templates = templatesGenerator(data);
    expect(templates).toHaveProperty("ChatInput");
    expect(templates).toHaveProperty("ChatOutput");
    expect(templates["ChatInput"].template.code.value).toBe("chat_code");
  });

  it("should skip components with flow property", () => {
    const data = asApiObject({
      models: {
        GroupNode: {
          template: {},
          flow: { data: { nodes: [] } },
        },
        Regular: {
          template: { code: { value: "code" } },
        },
      },
    });

    const templates = templatesGenerator(data);
    expect(templates).not.toHaveProperty("GroupNode");
    expect(templates).toHaveProperty("Regular");
  });

  describe("derived template aliases", () => {
    it("should add the legacy 'Prompt' alias for Prompt Template", () => {
      const data = asApiObject({
        models_and_agents: {
          "Prompt Template": {
            template: {
              code: { value: "prompt_v2_code" },
              _type: "Component",
            },
            display_name: "Prompt Template",
          },
        },
      });

      const templates = templatesGenerator(data);

      // Primary key
      expect(templates).toHaveProperty("Prompt Template");
      // Legacy alias for older flows
      expect(templates).toHaveProperty("Prompt");
      // Both should point to the same data
      expect(templates["Prompt"]).toBe(templates["Prompt Template"]);
    });

    it("should not overwrite existing direct key with alias", () => {
      const data = asApiObject({
        category: {
          Prompt: {
            template: { code: { value: "direct_code" } },
            display_name: "Prompt",
          },
          "Prompt Template": {
            template: {
              code: { value: "renamed_code" },
              _type: "Component",
            },
            display_name: "Prompt Template",
          },
        },
      });

      const templates = templatesGenerator(data);
      // "Prompt" exists as a direct key, so the derived alias should NOT overwrite it
      expect(templates["Prompt"].template.code.value).toBe("direct_code");
    });

    it("should derive a 'URL' alias from URLComponent", () => {
      const data = asApiObject({
        category: {
          URLComponent: {
            template: {
              code: { value: "url_code" },
              _type: "URLComponent",
            },
          },
        },
      });

      const templates = templatesGenerator(data);
      expect(templates).toHaveProperty("URLComponent");
      expect(templates).toHaveProperty("URL");
      expect(templates["URL"]).toBe(templates["URLComponent"]);
    });

    it("should add the legacy lowercase 'parser' alias for ParserComponent", () => {
      const data = asApiObject({
        processing: {
          ParserComponent: {
            template: {
              code: { value: "parser_code" },
              _type: "Component",
            },
            display_name: "Parser",
          },
        },
      });

      const templates = templatesGenerator(data);
      expect(templates).toHaveProperty("ParserComponent");
      expect(templates).toHaveProperty("Parser");
      expect(templates).toHaveProperty("parser");
      expect(templates["parser"]).toBe(templates["ParserComponent"]);
    });

    it("should derive bare and Component-stripped aliases from ext keys", () => {
      // Graduated bundle components are keyed ``ext:<bundle>:<Class>@<slot>``.
      // Flows saved before the move reference ``OpenAIModelComponent`` /
      // ``OpenAIModel``; both must resolve to the ext template so outdated
      // detection keeps working for legacy flows.
      const data = asApiObject({
        openai: {
          "ext:openai:OpenAIModelComponent@official": {
            template: {
              code: { value: "openai_code" },
              _type: "Component",
            },
            display_name: "OpenAI",
          },
        },
      });

      const templates = templatesGenerator(data);
      expect(templates).toHaveProperty(
        "ext:openai:OpenAIModelComponent@official",
      );
      expect(templates).toHaveProperty("OpenAIModelComponent");
      expect(templates).toHaveProperty("OpenAIModel");
      expect(templates["OpenAIModel"]).toBe(
        templates["ext:openai:OpenAIModelComponent@official"],
      );
    });

    it("should not let an ext-derived alias overwrite a built-in key", () => {
      const data = asApiObject({
        builtin: {
          Agent: {
            template: { code: { value: "builtin_agent_code" } },
            display_name: "Agent",
          },
        },
        somebundle: {
          "ext:somebundle:AgentComponent@official": {
            template: {
              code: { value: "bundle_agent_code" },
              _type: "Component",
            },
            display_name: "Agent",
          },
        },
      });

      const templates = templatesGenerator(data);
      expect(templates["Agent"].template.code.value).toBe("builtin_agent_code");
    });

    it("should handle components without metadata gracefully", () => {
      const data = asApiObject({
        category: {
          SimpleComponent: {
            template: { code: { value: "simple_code" } },
          },
        },
      });

      const templates = templatesGenerator(data);
      expect(templates).toHaveProperty("SimpleComponent");
      expect(Object.keys(templates)).toHaveLength(1);
    });
  });
});
