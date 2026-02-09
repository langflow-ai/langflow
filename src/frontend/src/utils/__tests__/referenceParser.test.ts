import {
  deduplicateSlug,
  generateBaseSlug,
  parseReferences,
  REFERENCE_PATTERN,
  RESERVED_SLUGS,
  VARS_SLUG,
} from "../referenceParser";

describe("referenceParser", () => {
  describe("parseReferences", () => {
    it("should parse a simple reference", () => {
      const refs = parseReferences("@NodeSlug.output");
      expect(refs).toHaveLength(1);
      expect(refs[0]).toEqual({
        nodeSlug: "NodeSlug",
        outputName: "output",
        dotPath: undefined,
        fullPath: "@NodeSlug.output",
        startIndex: 0,
        endIndex: 16,
      });
    });

    it("should parse a reference with dot path", () => {
      const refs = parseReferences("@Node.output.nested.path");
      expect(refs).toHaveLength(1);
      expect(refs[0].nodeSlug).toBe("Node");
      expect(refs[0].outputName).toBe("output");
      expect(refs[0].dotPath).toBe("nested.path");
    });

    it("should parse a reference with array index", () => {
      const refs = parseReferences("@Node.output[0]");
      expect(refs).toHaveLength(1);
      expect(refs[0].dotPath).toBe("[0]");
    });

    it("should parse a reference with mixed path", () => {
      const refs = parseReferences("@Node.output.items[0].name");
      expect(refs).toHaveLength(1);
      expect(refs[0].dotPath).toBe("items[0].name");
    });

    it("should parse multiple references", () => {
      const refs = parseReferences(
        "Hello @User.name, balance: @Account.balance",
      );
      expect(refs).toHaveLength(2);
      expect(refs[0].nodeSlug).toBe("User");
      expect(refs[0].outputName).toBe("name");
      expect(refs[1].nodeSlug).toBe("Account");
      expect(refs[1].outputName).toBe("balance");
    });

    it("should return empty array for no references", () => {
      const refs = parseReferences("Hello world");
      expect(refs).toHaveLength(0);
    });

    it("should return empty array for empty string", () => {
      const refs = parseReferences("");
      expect(refs).toHaveLength(0);
    });

    it("should not match incomplete reference (no output)", () => {
      const refs = parseReferences("@Node");
      expect(refs).toHaveLength(0);
    });

    it("should parse references with underscores", () => {
      const refs = parseReferences("@My_Node.output_name");
      expect(refs).toHaveLength(1);
      expect(refs[0].nodeSlug).toBe("My_Node");
      expect(refs[0].outputName).toBe("output_name");
    });

    it("should parse references with numbers", () => {
      const refs = parseReferences("@Node1.output2");
      expect(refs).toHaveLength(1);
      expect(refs[0].nodeSlug).toBe("Node1");
      expect(refs[0].outputName).toBe("output2");
    });

    it("should track correct start and end indices", () => {
      const text = "prefix @Node.out suffix";
      const refs = parseReferences(text);
      expect(refs).toHaveLength(1);
      expect(refs[0].startIndex).toBe(7);
      expect(refs[0].endIndex).toBe(16);
      expect(text.slice(refs[0].startIndex, refs[0].endIndex)).toBe(
        "@Node.out",
      );
    });

    it("should not match email addresses", () => {
      const refs = parseReferences("Email: user@domain.com");
      // The negative lookbehind prevents matching @ preceded by word chars
      expect(refs).toHaveLength(0);
    });

    it("should handle consecutive references without space (only first matches)", () => {
      const refs = parseReferences("@A.x@B.y");
      // Second @ is preceded by 'x' (word char), so not matched
      expect(refs).toHaveLength(1);
      expect(refs[0].nodeSlug).toBe("A");
    });

    it("should handle consecutive references with space", () => {
      const refs = parseReferences("@A.x @B.y");
      expect(refs).toHaveLength(2);
      expect(refs[0].nodeSlug).toBe("A");
      expect(refs[1].nodeSlug).toBe("B");
    });

    it("should handle reference in multiline text", () => {
      const refs = parseReferences("Line 1\n@Node.output\nLine 3");
      expect(refs).toHaveLength(1);
      expect(refs[0].nodeSlug).toBe("Node");
    });
  });

  describe("REFERENCE_PATTERN", () => {
    it("should be a global regex", () => {
      expect(REFERENCE_PATTERN.global).toBe(true);
    });
  });

  describe("edge cases", () => {
    it("should match reference at start of text", () => {
      const refs = parseReferences("@Node.output is the value");
      expect(refs).toHaveLength(1);
      expect(refs[0].startIndex).toBe(0);
    });

    it("should match reference at end of text", () => {
      const refs = parseReferences("The value is @Node.output");
      expect(refs).toHaveLength(1);
      expect(refs[0].endIndex).toBe(25);
    });

    it("should match reference after punctuation", () => {
      const refs = parseReferences("Check this: @Node.output!");
      expect(refs).toHaveLength(1);
      expect(refs[0].nodeSlug).toBe("Node");
    });

    it("should match reference after opening bracket", () => {
      const refs = parseReferences("Value is (@Node.output)");
      expect(refs).toHaveLength(1);
      expect(refs[0].nodeSlug).toBe("Node");
    });

    it("should match reference after opening brace", () => {
      const refs = parseReferences('{"key": @Node.output}');
      expect(refs).toHaveLength(1);
      expect(refs[0].nodeSlug).toBe("Node");
    });

    it("should handle multiple array indices", () => {
      const refs = parseReferences("@Node.output[0][1]");
      expect(refs).toHaveLength(1);
      expect(refs[0].dotPath).toBe("[0][1]");
    });

    it("should handle deeply nested paths", () => {
      const refs = parseReferences("@Node.output.a.b.c.d.e");
      expect(refs).toHaveLength(1);
      expect(refs[0].dotPath).toBe("a.b.c.d.e");
    });

    it("should handle mixed nested paths with arrays", () => {
      const refs = parseReferences("@Node.output.items[0].nested[1].value");
      expect(refs).toHaveLength(1);
      expect(refs[0].dotPath).toBe("items[0].nested[1].value");
    });

    it("should handle long node slugs", () => {
      const longSlug = "VeryLongNodeNameThatSomeoneCreated";
      const refs = parseReferences(`@${longSlug}.output`);
      expect(refs).toHaveLength(1);
      expect(refs[0].nodeSlug).toBe(longSlug);
    });

    it("should match reference after newline", () => {
      const refs = parseReferences("First line\n@Node.output");
      expect(refs).toHaveLength(1);
      expect(refs[0].nodeSlug).toBe("Node");
    });

    it("should match reference after tab", () => {
      const refs = parseReferences("Value:\t@Node.output");
      expect(refs).toHaveLength(1);
      expect(refs[0].nodeSlug).toBe("Node");
    });

    it("should not match @ in middle of word", () => {
      const refs = parseReferences("test@example.com");
      expect(refs).toHaveLength(0);
    });

    it("should match multiple references on same line", () => {
      const refs = parseReferences("@A.x + @B.y = @C.z");
      expect(refs).toHaveLength(3);
      expect(refs.map((r) => r.nodeSlug)).toEqual(["A", "B", "C"]);
    });

    it("should handle reference followed by comma", () => {
      const refs = parseReferences("Values: @A.x, @B.y");
      expect(refs).toHaveLength(2);
    });

    it("should not match if output name starts with number", () => {
      // \w includes numbers, so this should still match
      const refs = parseReferences("@Node.123output");
      expect(refs).toHaveLength(1);
      expect(refs[0].outputName).toBe("123output");
    });

    it("should handle reference in template literal style text", () => {
      const refs = parseReferences("Hello ${@User.name}!");
      expect(refs).toHaveLength(1);
      expect(refs[0].nodeSlug).toBe("User");
    });

    it("should produce stable results when called consecutively", () => {
      const text = "@A.x @B.y";
      const refs1 = parseReferences(text);
      const refs2 = parseReferences(text);
      expect(refs1).toHaveLength(2);
      expect(refs2).toHaveLength(2);
      expect(refs1[0].nodeSlug).toBe("A");
      expect(refs2[0].nodeSlug).toBe("A");
    });
  });

  describe("generateBaseSlug", () => {
    it("should convert display name to PascalCase slug", () => {
      expect(generateBaseSlug("Chat Input")).toBe("ChatInput");
    });

    it("should handle single word", () => {
      expect(generateBaseSlug("Agent")).toBe("Agent");
    });

    it("should remove non-alphanumeric characters", () => {
      expect(generateBaseSlug("API (v2)")).toBe("APIv2");
    });

    it("should capitalize first letter of each word", () => {
      expect(generateBaseSlug("http request")).toBe("HttpRequest");
    });

    it("should return Node for empty string", () => {
      expect(generateBaseSlug("")).toBe("Node");
    });

    it("should handle leading/trailing whitespace", () => {
      expect(generateBaseSlug("  Chat Input  ")).toBe("ChatInput");
    });

    it("should handle multiple consecutive spaces", () => {
      expect(generateBaseSlug("Chat   Input")).toBe("ChatInput");
    });

    it("should preserve existing uppercase in non-first position", () => {
      expect(generateBaseSlug("OpenAI LLM")).toBe("OpenAILLM");
    });
  });

  describe("deduplicateSlug", () => {
    it("should return baseSlug when no collision", () => {
      expect(deduplicateSlug("ChatInput", [])).toBe("ChatInput");
      expect(deduplicateSlug("ChatInput", ["Agent"])).toBe("ChatInput");
    });

    it("should append _1 on first collision", () => {
      expect(deduplicateSlug("ChatInput", ["ChatInput"])).toBe("ChatInput_1");
    });

    it("should increment counter for sequential collisions", () => {
      expect(deduplicateSlug("ChatInput", ["ChatInput", "ChatInput_1"])).toBe(
        "ChatInput_2",
      );
    });

    it("should fill gaps in numbering", () => {
      expect(deduplicateSlug("ChatInput", ["ChatInput", "ChatInput_2"])).toBe(
        "ChatInput_1",
      );
    });

    it("should handle many collisions", () => {
      const existing = ["Node", "Node_1", "Node_2", "Node_3", "Node_4"];
      expect(deduplicateSlug("Node", existing)).toBe("Node_5");
    });

    it("should not collide with different base slugs", () => {
      expect(deduplicateSlug("ChatInput", ["ChatOutput", "Agent"])).toBe(
        "ChatInput",
      );
    });
  });

  describe("RESERVED_SLUGS and VARS_SLUG", () => {
    it("should have Vars as the VARS_SLUG constant", () => {
      expect(VARS_SLUG).toBe("Vars");
    });

    it("should include Vars in RESERVED_SLUGS", () => {
      expect(RESERVED_SLUGS).toContain("Vars");
    });

    it("should prevent reserved slug from being used via deduplicateSlug", () => {
      // When existing slugs include Vars, deduplicateSlug avoids it
      const existing = [...RESERVED_SLUGS];
      expect(existing).toContain("Vars");
      expect(deduplicateSlug("Vars", existing)).toBe("Vars_1");
    });

    it("should parse @Vars.variable_name as a valid reference", () => {
      const refs = parseReferences("@Vars.my_var");
      expect(refs).toHaveLength(1);
      expect(refs[0].nodeSlug).toBe("Vars");
      expect(refs[0].outputName).toBe("my_var");
    });

    it("should parse @Vars.var alongside regular references", () => {
      const refs = parseReferences("@ChatInput.message and @Vars.api_key");
      expect(refs).toHaveLength(2);
      expect(refs[0].nodeSlug).toBe("ChatInput");
      expect(refs[1].nodeSlug).toBe("Vars");
      expect(refs[1].outputName).toBe("api_key");
    });
  });
});
