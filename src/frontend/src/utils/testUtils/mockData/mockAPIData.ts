import type {
  APIClassType,
  APIDataType,
  APITemplateType,
  InputFieldType,
} from "@/types/api";

const mockTemplate: APITemplateType = {
  api_key: {
    load_from_db: true,
    required: true,
    placeholder: "",
    show: true,
    list: false,
    readonly: false,
    name: "api_key",
    value: "",
    display_name: "API Key",
    advanced: false,
    input_types: [],
    dynamic: false,
    info: "Your Mock Component API key",
    title_case: false,
    password: true,
    type: "str",
    _input_type: "SecretStrInput",
  },
};

const mockAPIData: APIDataType = {
  mockComponent: {
    MockComponent: {
      template: mockTemplate,
      description: "mocks the component",
      icon: "cirleQuestionMark",
      base_classes: ["Data"],
      display_name: "Mock Component",
      documentation: "https://docs.langflow.org/",
      minimized: false,
      custom_fields: {},
      output_types: [],
      pinned: false,
      conditional_paths: [],
      frozen: false,
      outputs: [],
      field_order: ["api_key"],
      beta: false,
      legacy: false,
      edited: false,
      tool_mode: false,
    },
  },
};

export default mockAPIData;
