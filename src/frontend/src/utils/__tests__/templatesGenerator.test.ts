import { templatesGenerator } from "../reactflowUtils";

describe("templatesGenerator", () => {
  it("should create templates indexed by component key", () => {
    const data = {
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
    };

    const templates = templatesGenerator(data);
    expect(templates).toHaveProperty("ChatInput");
    expect(templates).toHaveProperty("ChatOutput");
    expect(templates["ChatInput"].template.code.value).toBe("chat_code");
  });

  it("should skip components with flow property", () => {
    const data = {
      models: {
        GroupNode: {
          template: {},
          flow: { data: { nodes: [] } },
        },
        Regular: {
          template: { code: { value: "code" } },
        },
      },
    };

    const templates = templatesGenerator(data);
    expect(templates).not.toHaveProperty("GroupNode");
    expect(templates).toHaveProperty("Regular");
  });

  describe("LEGACY_TYPE_ALIASES", () => {
    it("should add 'Prompt' alias pointing to 'Prompt Template'", () => {
      const data = {
        models_and_agents: {
          "Prompt Template": {
            template: { code: { value: "prompt_v2_code" } },
            display_name: "Prompt Template",
          },
        },
      };

      const templates = templatesGenerator(data);

      // Primary key
      expect(templates).toHaveProperty("Prompt Template");
      // Alias from LEGACY_TYPE_ALIASES: "Prompt" -> "Prompt Template"
      expect(templates).toHaveProperty("Prompt");
      // Both should point to the same data
      expect(templates["Prompt"]).toBe(templates["Prompt Template"]);
    });

    it("should not overwrite existing direct key with alias", () => {
      const data = {
        category: {
          Prompt: {
            template: { code: { value: "direct_code" } },
            display_name: "Prompt",
          },
          "Prompt Template": {
            template: { code: { value: "renamed_code" } },
            display_name: "Prompt Template",
          },
        },
      };

      const templates = templatesGenerator(data);
      // "Prompt" exists as a direct key, so the alias should NOT overwrite it
      expect(templates["Prompt"].template.code.value).toBe("direct_code");
    });

    it("should not add alias when target does not exist", () => {
      const data = {
        category: {
          ChatInput: {
            template: { code: { value: "code" } },
          },
        },
      };

      const templates = templatesGenerator(data);
      // "Prompt Template" doesn't exist, so "Prompt" alias should not be added
      expect(templates).not.toHaveProperty("Prompt");
      expect(templates).toHaveProperty("ChatInput");
    });

    it("should handle components without metadata gracefully", () => {
      const data = {
        category: {
          SimpleComponent: {
            template: { code: { value: "simple_code" } },
          },
        },
      };

      const templates = templatesGenerator(data);
      expect(templates).toHaveProperty("SimpleComponent");
      expect(Object.keys(templates)).toHaveLength(1);
    });
  });
});
