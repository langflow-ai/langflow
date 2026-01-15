import { TAB_TYPES } from "@/types/global_variables";
import { assignTab } from "../utils/assign-tab";

describe("GlobalVariableModal - assignTab Function", () => {
  describe("Basic Functionality", () => {
    it("should convert 'credential' (lowercase) to 'Credential'", () => {
      const result = assignTab("credential");
      expect(result).toBe("Credential");
    });

    it("should convert 'generic' (lowercase) to 'Generic'", () => {
      const result = assignTab("generic");
      expect(result).toBe("Generic");
    });

    it("should preserve 'Credential' input", () => {
      const result = assignTab("Credential");
      expect(result).toBe("Credential");
    });

    it("should preserve 'Generic' input", () => {
      const result = assignTab("Generic");
      expect(result).toBe("Generic");
    });
  });

  describe("Case Insensitivity", () => {
    it("should handle uppercase 'CREDENTIAL'", () => {
      const result = assignTab("CREDENTIAL");
      expect(result).toBe("Credential");
    });

    it("should handle uppercase 'GENERIC'", () => {
      const result = assignTab("GENERIC");
      expect(result).toBe("Generic");
    });

    it("should handle mixed case 'CrEdEnTiAl'", () => {
      const result = assignTab("CrEdEnTiAl");
      expect(result).toBe("Credential");
    });

    it("should handle mixed case 'GeNeRiC'", () => {
      const result = assignTab("GeNeRiC");
      expect(result).toBe("Generic");
    });
  });

  describe("Default Behavior", () => {
    it("should default to 'Credential' for unknown input", () => {
      const result = assignTab("unknown");
      expect(result).toBe("Credential");
    });

    it("should default to 'Credential' for empty string", () => {
      const result = assignTab("");
      expect(result).toBe("Credential");
    });

    it("should default to 'Credential' for whitespace", () => {
      const result = assignTab("   ");
      expect(result).toBe("Credential");
    });

    it("should default to 'Credential' for special characters", () => {
      const result = assignTab("@#$%");
      expect(result).toBe("Credential");
    });

    it("should default to 'Credential' for numeric input", () => {
      const result = assignTab("123");
      expect(result).toBe("Credential");
    });

    it("should default to 'Credential' for null/undefined converted to string", () => {
      const result = assignTab("null");
      expect(result).toBe("Credential");
    });
  });

  describe("Edge Cases", () => {
    it("should handle 'credential ' with trailing space", () => {
      const result = assignTab("credential ");
      expect(result).toBe("Credential");
    });

    it("should handle ' credential' with leading space", () => {
      const result = assignTab(" credential");
      expect(result).toBe("Credential");
    });

    it("should handle multiple spaces around input", () => {
      const result = assignTab("  generic  ");
      expect(result).toBe("Generic");
    });
  });

  describe("Return Type Safety", () => {
    it("should always return a valid TAB_TYPES value", () => {
      const validTypes: TAB_TYPES[] = ["Credential", "Generic"];

      const inputs = [
        "credential",
        "generic",
        "Credential",
        "Generic",
        "unknown",
        "",
      ];

      inputs.forEach((input) => {
        const result = assignTab(input);
        expect(validTypes).toContain(result);
      });
    });
  });
});

describe("GlobalVariableModal - Type Safety & onValueChange", () => {
  describe("Tab Type Definitions", () => {
    it("should define TAB_TYPES as union of 'Credential' and 'Generic'", () => {
      const credentialType: TAB_TYPES = "Credential";
      const genericType: TAB_TYPES = "Generic";

      expect(credentialType).toBe("Credential");
      expect(genericType).toBe("Generic");
    });
  });
});
