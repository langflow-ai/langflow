import { act, renderHook } from "@testing-library/react";
import type { APIClassType, APIDataType } from "../../types/api";
import { useTypesStore } from "../typesStore";

// Mock the complex utility functions
jest.mock("../../utils/reactflowUtils", () => ({
  extractSecretFieldsFromComponents: jest.fn(
    (data) => new Set(Object.keys(data)),
  ),
  templatesGenerator: jest.fn((data) => {
    const templates = {};
    Object.keys(data).forEach((key) => {
      templates[key] = { template: data[key] };
    });
    return templates;
  }),
  typesGenerator: jest.fn((data) => {
    const types = {};
    Object.keys(data).forEach((key) => {
      types[key] = typeof data[key];
    });
    return types;
  }),
}));

// Mock imports
const mockExtractSecretFieldsFromComponents =
  require("../../utils/reactflowUtils").extractSecretFieldsFromComponents;
const mockTemplatesGenerator =
  require("../../utils/reactflowUtils").templatesGenerator;
const mockTypesGenerator = require("../../utils/reactflowUtils").typesGenerator;

const mockAPIData: APIDataType = {
  TextInput: {
    template: {
      value: {
        type: "str",
        required: true,
        placeholder: "Enter text",
      },
    },
    description: "Text input component",
  },
  NumberInput: {
    template: {
      value: {
        type: "int",
        required: false,
        placeholder: "Enter number",
      },
    },
    description: "Number input component",
  },
};

const mockAPIData2: APIDataType = {
  BooleanInput: {
    template: {
      value: {
        type: "bool",
        required: true,
      },
    },
    description: "Boolean input component",
  },
};

const mockTemplates = {
  TextInput: { template: mockAPIData.TextInput },
  NumberInput: { template: mockAPIData.NumberInput },
};

const mockTypes = {
  TextInput: "object",
  NumberInput: "object",
};

describe("useTypesStore", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Reset mock implementations
    mockExtractSecretFieldsFromComponents.mockImplementation((data) => {
      if (!data || typeof data !== "object") return new Set();
      return new Set(Object.keys(data));
    });
    mockTemplatesGenerator.mockReturnValue({});
    mockTypesGenerator.mockReturnValue({});

    act(() => {
      useTypesStore.setState({
        ComponentFields: new Set(),
        types: {},
        templates: {},
        data: {},
      });
    });
  });

  describe("initial state", () => {
    it("should have correct initial state", () => {
      const { result } = renderHook(() => useTypesStore());

      expect(result.current.ComponentFields).toEqual(new Set());
      expect(result.current.types).toEqual({});
      expect(result.current.templates).toEqual({});
      expect(result.current.data).toEqual({});
    });
  });

  describe("setComponentFields", () => {
    it("should set component fields", () => {
      const { result } = renderHook(() => useTypesStore());
      const fields = new Set(["field1", "field2", "field3"]);

      act(() => {
        result.current.setComponentFields(fields);
      });

      expect(result.current.ComponentFields).toEqual(fields);
    });

    it("should replace existing component fields", () => {
      const { result } = renderHook(() => useTypesStore());
      const initialFields = new Set(["initial1", "initial2"]);
      const newFields = new Set(["new1", "new2", "new3"]);

      act(() => {
        result.current.setComponentFields(initialFields);
      });
      expect(result.current.ComponentFields).toEqual(initialFields);

      act(() => {
        result.current.setComponentFields(newFields);
      });
      expect(result.current.ComponentFields).toEqual(newFields);
    });

    it("should handle empty Set", () => {
      const { result } = renderHook(() => useTypesStore());
      const emptySet = new Set();

      act(() => {
        result.current.setComponentFields(emptySet);
      });

      expect(result.current.ComponentFields).toEqual(emptySet);
    });
  });

  describe("addComponentField", () => {
    it("should add single field to empty set", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.addComponentField("newField");
      });

      expect(result.current.ComponentFields.has("newField")).toBe(true);
      expect(result.current.ComponentFields.size).toBe(1);
    });

    it("should add field to existing set", () => {
      const { result } = renderHook(() => useTypesStore());
      const initialFields = new Set(["existing1", "existing2"]);

      act(() => {
        result.current.setComponentFields(initialFields);
      });

      act(() => {
        result.current.addComponentField("newField");
      });

      expect(result.current.ComponentFields.has("existing1")).toBe(true);
      expect(result.current.ComponentFields.has("existing2")).toBe(true);
      expect(result.current.ComponentFields.has("newField")).toBe(true);
      expect(result.current.ComponentFields.size).toBe(3);
    });

    it("should not add duplicate field", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.addComponentField("duplicate");
      });
      expect(result.current.ComponentFields.size).toBe(1);

      act(() => {
        result.current.addComponentField("duplicate");
      });
      expect(result.current.ComponentFields.size).toBe(1);
      expect(result.current.ComponentFields.has("duplicate")).toBe(true);
    });

    it("should handle empty string field", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.addComponentField("");
      });

      expect(result.current.ComponentFields.has("")).toBe(true);
      expect(result.current.ComponentFields.size).toBe(1);
    });
  });

  describe("setTypes", () => {
    it("should set types, templates, data, and component fields", () => {
      mockTypesGenerator.mockReturnValue(mockTypes);
      mockTemplatesGenerator.mockReturnValue(mockTemplates);
      mockExtractSecretFieldsFromComponents.mockReturnValue(
        new Set(["TextInput", "NumberInput"]),
      );

      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.setTypes(mockAPIData);
      });

      expect(mockTypesGenerator).toHaveBeenCalledWith(mockAPIData);
      expect(mockTemplatesGenerator).toHaveBeenCalledWith(mockAPIData);
      expect(mockExtractSecretFieldsFromComponents).toHaveBeenCalledWith(
        mockAPIData,
      );

      expect(result.current.types).toEqual(mockTypes);
      expect(result.current.templates).toEqual(mockTemplates);
      expect(result.current.data).toEqual(mockAPIData);
      expect(result.current.ComponentFields).toEqual(
        new Set(["TextInput", "NumberInput"]),
      );
    });

    it("should merge with existing data", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.setTypes(mockAPIData);
      });

      act(() => {
        result.current.setTypes(mockAPIData2);
      });

      expect(result.current.data).toEqual({ ...mockAPIData, ...mockAPIData2 });
      expect(mockExtractSecretFieldsFromComponents).toHaveBeenCalledWith({
        ...mockAPIData,
        ...mockAPIData2,
      });
    });

    it("should handle empty API data", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.setTypes({});
      });

      expect(mockTypesGenerator).toHaveBeenCalledWith({});
      expect(mockTemplatesGenerator).toHaveBeenCalledWith({});
      expect(mockExtractSecretFieldsFromComponents).toHaveBeenCalledWith({});
    });

    it("should overwrite duplicate keys in data", () => {
      const { result } = renderHook(() => useTypesStore());
      const updatedData = {
        TextInput: {
          template: {
            value: {
              type: "str",
              required: false, // Changed from true
              placeholder: "Updated placeholder",
            },
          },
          description: "Updated text input component",
        },
      };

      act(() => {
        result.current.setTypes(mockAPIData);
      });

      act(() => {
        result.current.setTypes(updatedData);
      });

      expect(result.current.data["TextInput"]).toEqual(
        updatedData["TextInput"],
      );
    });
  });

  describe("setTemplates", () => {
    it("should set templates object", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.setTemplates(mockTemplates);
      });

      expect(result.current.templates).toEqual(mockTemplates);
    });

    it("should replace existing templates", () => {
      const { result } = renderHook(() => useTypesStore());
      const newTemplates = {
        CustomComponent: { template: { prop: "value" } },
      };

      act(() => {
        result.current.setTemplates(mockTemplates);
      });
      expect(result.current.templates).toEqual(mockTemplates);

      act(() => {
        result.current.setTemplates(newTemplates);
      });
      expect(result.current.templates).toEqual(newTemplates);
    });

    it("should handle empty templates object", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.setTemplates({});
      });

      expect(result.current.templates).toEqual({});
    });

    it("should handle complex template structures", () => {
      const { result } = renderHook(() => useTypesStore());
      const complexTemplates = {
        ComplexComponent: {
          template: {
            nestedProp: {
              subProp: "value",
              arrayProp: [1, 2, 3],
            },
          },
        },
      };

      act(() => {
        result.current.setTemplates(complexTemplates);
      });

      expect(result.current.templates).toEqual(complexTemplates);
    });
  });

  describe("setData", () => {
    it("should set data with object", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.setData(mockAPIData);
      });

      expect(result.current.data).toEqual(mockAPIData);
      expect(mockExtractSecretFieldsFromComponents).toHaveBeenCalledWith(
        mockAPIData,
      );
    });

    it("should set data with function", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.setData(mockAPIData);
      });

      act(() => {
        result.current.setData((oldData) => ({
          ...oldData,
          ...mockAPIData2,
        }));
      });

      expect(result.current.data).toEqual({ ...mockAPIData, ...mockAPIData2 });
      expect(mockExtractSecretFieldsFromComponents).toHaveBeenLastCalledWith({
        ...mockAPIData,
        ...mockAPIData2,
      });
    });

    it("should call setComponentFields after setting data", () => {
      const { result } = renderHook(() => useTypesStore());
      const expectedFields = new Set(["field1", "field2"]);
      mockExtractSecretFieldsFromComponents.mockReturnValue(expectedFields);

      act(() => {
        result.current.setData(mockAPIData);
      });

      expect(result.current.ComponentFields).toEqual(expectedFields);
    });

    it("should handle function that returns empty object", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.setData(mockAPIData);
      });

      act(() => {
        result.current.setData(() => ({}));
      });

      expect(result.current.data).toEqual({});
      expect(mockExtractSecretFieldsFromComponents).toHaveBeenLastCalledWith(
        {},
      );
    });

    it("should handle function that modifies existing data", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.setData(mockAPIData);
      });

      act(() => {
        result.current.setData((oldData) => {
          const newData = { ...oldData };
          delete newData["NumberInput"];
          return newData;
        });
      });

      expect(result.current.data).not.toHaveProperty("NumberInput");
      expect(result.current.data).toHaveProperty("TextInput");
    });
  });

  describe("state interactions", () => {
    it("should handle complex state updates", () => {
      mockTypesGenerator.mockReturnValue({ TestComponent: "object" });
      mockTemplatesGenerator.mockReturnValue({
        TestComponent: { template: {} },
      });
      mockExtractSecretFieldsFromComponents.mockReturnValue(
        new Set(["TestComponent"]),
      );

      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.setTypes(mockAPIData);
        result.current.addComponentField("additionalField");
        result.current.setTemplates({ CustomTemplate: { template: {} } });
      });

      expect(result.current.data).toEqual(mockAPIData);
      expect(result.current.ComponentFields.has("additionalField")).toBe(true);
      expect(result.current.templates).toHaveProperty("CustomTemplate");
    });

    it("should maintain state consistency across multiple operations", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.setComponentFields(new Set(["field1"]));
        result.current.addComponentField("field2");
      });

      // setData will call setComponentFields internally, so track the fields before
      const fieldsBeforeSetData = new Set(result.current.ComponentFields);

      act(() => {
        result.current.setData(mockAPIData);
        result.current.addComponentField("field3");
      });

      // The setData call will replace ComponentFields, so check for field3
      expect(result.current.ComponentFields.has("field3")).toBe(true);
      expect(result.current.data).toEqual(mockAPIData);
    });
  });

  describe("edge cases", () => {
    it("should handle null/undefined data", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.setData(null as any);
      });

      expect(result.current.data).toBeNull();
    });

    it("should handle complex nested API data", () => {
      const complexData = {
        NestedComponent: {
          template: {
            prop1: {
              nested: {
                deep: {
                  value: "deep-value",
                },
              },
            },
          },
          metadata: {
            version: "1.0.0",
            author: "test",
          },
        },
      };

      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.setTypes(complexData);
      });

      expect(mockTypesGenerator).toHaveBeenCalledWith(complexData);
      expect(mockTemplatesGenerator).toHaveBeenCalledWith(complexData);
      expect(result.current.data).toEqual(complexData);
    });

    it("should handle large ComponentFields sets", () => {
      const { result } = renderHook(() => useTypesStore());
      const largeSet = new Set();

      for (let i = 0; i < 1000; i++) {
        largeSet.add(`field-${i}`);
      }

      act(() => {
        result.current.setComponentFields(largeSet);
      });

      expect(result.current.ComponentFields.size).toBe(1000);
      expect(result.current.ComponentFields.has("field-500")).toBe(true);
    });

    it("should handle rapid consecutive updates", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        for (let i = 0; i < 10; i++) {
          result.current.addComponentField(`rapid-field-${i}`);
        }
      });

      expect(result.current.ComponentFields.size).toBe(10);
      for (let i = 0; i < 10; i++) {
        expect(result.current.ComponentFields.has(`rapid-field-${i}`)).toBe(
          true,
        );
      }
    });

    it("should handle circular data references in function updates", () => {
      const { result } = renderHook(() => useTypesStore());

      act(() => {
        result.current.setData({ initial: "data" });
      });

      act(() => {
        result.current.setData((oldData) => ({
          ...oldData,
          self: oldData, // Circular reference
          additional: "value",
        }));
      });

      expect(result.current.data).toHaveProperty("initial");
      expect(result.current.data).toHaveProperty("additional");
      expect(result.current.data).toHaveProperty("self");
    });
  });
});
