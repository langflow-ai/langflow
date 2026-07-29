import type { APIClassType, InputFieldType } from "@/types/api";
import InputGlobalComponent from "../../inputGlobalComponent";
import { StrRenderComponent } from "..";

jest.mock("../../copyFieldAreaComponent", () => () => null);
jest.mock("../../dropdownComponent", () => () => null);
jest.mock("../../inputGlobalComponent", () => () => null);
jest.mock("../../textAreaComponent", () => () => null);
jest.mock("../../webhookFieldComponent", () => () => null);

const templateField = (
  overrides: Partial<InputFieldType> = {},
): InputFieldType => ({
  type: "str",
  required: false,
  list: false,
  show: true,
  readonly: false,
  ...overrides,
});

describe("StrRenderComponent", () => {
  it("passes the node definition to global-variable inputs", () => {
    const nodeClass: APIClassType = {
      description: "",
      display_name: "Embedding Model",
      documentation: "",
      template: {
        api_key: templateField({ display_name: "API Key" }),
        model: templateField({
          _input_type: "ModelInput",
          type: "model",
        }),
      },
    };

    const element = StrRenderComponent({
      id: "str_api_key",
      value: "",
      editNode: false,
      handleOnNewValue: jest.fn(),
      disabled: false,
      nodeClass,
      templateData: templateField({
        name: "api_key",
        display_name: "API Key",
        load_from_db: false,
        password: true,
      }),
      name: "api_key",
      display_name: "API Key",
      nodeId: "node-id",
      handleNodeClass: jest.fn(),
    });

    expect(element?.type).toBe(InputGlobalComponent);
    expect(element?.props.nodeClass).toBe(nodeClass);
    expect(element?.props.id).toBe("input-api_key");
  });
});
