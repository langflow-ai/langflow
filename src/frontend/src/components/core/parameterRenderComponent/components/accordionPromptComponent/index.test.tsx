// Tests for AccordionPromptComponent functionality
// Testing the actual generateUniqueVariableName function from the component

import { generateUniqueVariableName } from "./index";

describe("AccordionPromptComponent", () => {
  describe("generateUniqueVariableName", () => {
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
});
