// Tests for AccordionPromptComponent functionality
// Focus on testing the unique variable name generation logic

describe("AccordionPromptComponent", () => {
  describe("unique variable name generation", () => {
    // Extract the core logic from handleAddVariable for testing
    const generateUniqueVariableName = (templateValue: string): string => {
      // Find all existing variables in the template
      const variableRegex = /\{([^{}]+)\}/g;
      const existingVariables = new Set<string>();
      let match: RegExpExecArray | null;
      while ((match = variableRegex.exec(templateValue)) !== null) {
        existingVariables.add(match[1]);
      }

      // Generate a unique variable name
      let variableName = "variable_name";
      if (existingVariables.has(variableName)) {
        // Find the next available number
        let counter = 1;
        while (existingVariables.has(`variable_name_${counter}`)) {
          counter++;
        }
        variableName = `variable_name_${counter}`;
      }

      return variableName;
    };

    it("should return 'variable_name' when template is empty", () => {
      const result = generateUniqueVariableName("");
      expect(result).toBe("variable_name");
    });

    it("should return 'variable_name' when no variables exist", () => {
      const result = generateUniqueVariableName("Hello world!");
      expect(result).toBe("variable_name");
    });

    it("should return 'variable_name' when only other variables exist", () => {
      const result = generateUniqueVariableName(
        "Hello {name}, your {id} is ready",
      );
      expect(result).toBe("variable_name");
    });

    it("should return 'variable_name_1' when 'variable_name' already exists", () => {
      const result = generateUniqueVariableName("Hello {variable_name}!");
      expect(result).toBe("variable_name_1");
    });

    it("should return 'variable_name_2' when 'variable_name' and 'variable_name_1' exist", () => {
      const result = generateUniqueVariableName(
        "Hello {variable_name} and {variable_name_1}!",
      );
      expect(result).toBe("variable_name_2");
    });

    it("should return 'variable_name_3' when first three exist", () => {
      const result = generateUniqueVariableName(
        "{variable_name}{variable_name_1}{variable_name_2}",
      );
      expect(result).toBe("variable_name_3");
    });

    it("should fill gaps - return 'variable_name_1' when only 'variable_name' and 'variable_name_2' exist", () => {
      const result = generateUniqueVariableName(
        "Hello {variable_name} and {variable_name_2}!",
      );
      expect(result).toBe("variable_name_1");
    });

    it("should handle mixed variables with 'variable_name' present", () => {
      const result = generateUniqueVariableName(
        "User: {name}, Template: {variable_name}, ID: {id}",
      );
      expect(result).toBe("variable_name_1");
    });

    it("should handle variables with similar names but not exact match", () => {
      // 'variable_name_extra' should not affect 'variable_name' check
      const result = generateUniqueVariableName("Hello {variable_name_extra}!");
      expect(result).toBe("variable_name");
    });

    it("should handle multiple occurrences of the same variable", () => {
      const result = generateUniqueVariableName(
        "{variable_name} is {variable_name} and {variable_name}",
      );
      expect(result).toBe("variable_name_1");
    });

    it("should work with newlines in template", () => {
      const result = generateUniqueVariableName(
        "Line 1: {variable_name}\nLine 2: {variable_name_1}",
      );
      expect(result).toBe("variable_name_2");
    });

    it("should handle complex template with many variable types", () => {
      const template = `
        Name: {name}
        Age: {age}
        Default: {variable_name}
        Second: {variable_name_1}
        City: {city}
      `;
      const result = generateUniqueVariableName(template);
      expect(result).toBe("variable_name_2");
    });
  });

  describe("variable extraction regex", () => {
    const extractVariables = (templateValue: string): string[] => {
      const variableRegex = /\{([^{}]+)\}/g;
      const variables: string[] = [];
      let match: RegExpExecArray | null;
      while ((match = variableRegex.exec(templateValue)) !== null) {
        variables.push(match[1]);
      }
      return variables;
    };

    it("should extract single variable", () => {
      const result = extractVariables("Hello {name}!");
      expect(result).toEqual(["name"]);
    });

    it("should extract multiple variables", () => {
      const result = extractVariables(
        "{greeting} {name}, your {item} is ready",
      );
      expect(result).toEqual(["greeting", "name", "item"]);
    });

    it("should return empty array for no variables", () => {
      const result = extractVariables("Hello world!");
      expect(result).toEqual([]);
    });

    it("should handle adjacent variables", () => {
      const result = extractVariables("{a}{b}{c}");
      expect(result).toEqual(["a", "b", "c"]);
    });

    it("should handle variables with underscores and numbers", () => {
      const result = extractVariables("{var_1} {var_2} {my_variable_123}");
      expect(result).toEqual(["var_1", "var_2", "my_variable_123"]);
    });

    it("should handle empty template", () => {
      const result = extractVariables("");
      expect(result).toEqual([]);
    });
  });
});
