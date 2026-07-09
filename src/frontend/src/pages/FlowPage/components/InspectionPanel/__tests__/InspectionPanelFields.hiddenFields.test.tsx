import { render, screen } from "@testing-library/react";
import type { NodeDataType } from "@/types/flow";
import InspectionPanelFields from "../components/InspectionPanelFields";

// Only the heavy leaf inputs are mocked; the field-filtering logic and the
// real HIDDEN_FIELDS list run unmocked so this exercises the actual behavior.
jest.mock("../components/InspectionPanelField", () => {
  return function MockInspectionPanelField({ name }: { name: string }) {
    return <div data-testid={`field-${name}`} />;
  };
});

jest.mock("../components/InspectionPanelEditField", () => {
  return function MockInspectionPanelEditField({ name }: { name: string }) {
    return <div data-testid={`edit-field-${name}`} />;
  };
});

// Regression coverage for https://github.com/langflow-ai/langflow/issues/13595
// A field listed in HIDDEN_FIELDS (ChatInput.should_store_message) must be
// hidden from the default advanced view yet remain reachable in edit mode, so
// users keep a path to surface and edit it.
describe("InspectionPanelFields — HIDDEN_FIELDS reachability (issue #13595)", () => {
  const createChatInputData = (): NodeDataType =>
    ({
      id: "chat-input-1",
      type: "ChatInput",
      node: {
        display_name: "Chat Input",
        description: "",
        template: {
          // Listed in HIDDEN_FIELDS for ChatInput; advanced + shown.
          should_store_message: {
            type: "bool",
            value: true,
            advanced: true,
            show: true,
            display_name: "Store Messages",
          },
          // A regular advanced field that is NOT hidden.
          temperature: {
            type: "float",
            value: 0.1,
            advanced: true,
            show: true,
            display_name: "Temperature",
          },
        },
        field_order: [],
      },
    }) as unknown as NodeDataType;

  it("hides the field from the default advanced view", () => {
    render(
      <InspectionPanelFields
        data={createChatInputData()}
        isEditingFields={false}
      />,
    );

    expect(
      screen.queryByTestId("field-should_store_message"),
    ).not.toBeInTheDocument();
    // A non-hidden advanced field still renders.
    expect(screen.getByTestId("field-temperature")).toBeInTheDocument();
  });

  it("surfaces the field in edit mode so it stays editable", () => {
    render(
      <InspectionPanelFields
        data={createChatInputData()}
        isEditingFields={true}
      />,
    );

    expect(
      screen.getByTestId("edit-field-should_store_message"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("edit-field-temperature")).toBeInTheDocument();
  });

  // The Agent HIDDEN_FIELDS entry once listed a stale `verbose` field that was
  // dropped from the component (drop = {"verbose"}); cleaning that up must not
  // also surface the live format_instructions / output_schema advanced inputs.
  const createAgentData = (): NodeDataType =>
    ({
      id: "agent-1",
      type: "Agent",
      node: {
        display_name: "Agent",
        description: "",
        template: {
          format_instructions: {
            type: "str",
            value: "",
            advanced: true,
            show: true,
            display_name: "Output Format Instructions",
          },
          output_schema: {
            type: "table",
            value: [],
            advanced: true,
            show: true,
            display_name: "Output Schema",
          },
        },
        field_order: [],
      },
    }) as unknown as NodeDataType;

  it("keeps Agent format_instructions/output_schema hidden from the default view but editable", () => {
    const { rerender } = render(
      <InspectionPanelFields
        data={createAgentData()}
        isEditingFields={false}
      />,
    );

    expect(
      screen.queryByTestId("field-format_instructions"),
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId("field-output_schema")).not.toBeInTheDocument();

    rerender(
      <InspectionPanelFields data={createAgentData()} isEditingFields={true} />,
    );

    expect(
      screen.getByTestId("edit-field-format_instructions"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("edit-field-output_schema")).toBeInTheDocument();
  });
});
