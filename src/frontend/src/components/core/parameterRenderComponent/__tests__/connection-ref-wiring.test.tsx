import { render } from "@testing-library/react";
import { ParameterRenderComponent } from "..";

// ParameterRenderComponent's module-level imports pull in every widget it can
// dispatch to, so each needs a trivial stub for the module to load (see
// aria-labelledby.test.tsx). Only the connection_ref seam is inspected here.
const mockConnectionRef = jest.fn((_props: Record<string, unknown>) => (
  <div data-testid="picker" />
));
jest.mock("@/customization/components/custom-connectionRefComponent", () => ({
  __esModule: true,
  default: (props: Record<string, unknown>) => mockConnectionRef(props),
}));
jest.mock(
  "@/components/core/parameterRenderComponent/components/codeAreaComponent",
  () => () => <div data-testid="widget" />,
);
jest.mock(
  "@/components/core/parameterRenderComponent/components/dataDisplayComponent",
  () => () => <div data-testid="widget" />,
);
jest.mock(
  "@/components/core/parameterRenderComponent/components/dbProviderInputComponent",
  () => () => <div data-testid="widget" />,
);
jest.mock(
  "@/components/core/parameterRenderComponent/components/modelInputComponent",
  () => () => <div data-testid="widget" />,
);
jest.mock(
  "@/components/core/parameterRenderComponent/components/sliderComponent",
  () => () => <div data-testid="widget" />,
);
jest.mock(
  "@/components/core/parameterRenderComponent/components/TableNodeComponent",
  () => () => <div data-testid="widget" />,
);
jest.mock(
  "@/components/core/parameterRenderComponent/components/tabComponent",
  () => () => <div data-testid="widget" />,
);
jest.mock("@/customization/components/custom-connectionComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("@/customization/components/custom-input-file", () => () => (
  <div data-testid="widget" />
));
jest.mock("@/customization/components/custom-linkComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/accordionPromptComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/actionPickerComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/dictComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/durationComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/emptyParameterComponent", () => ({
  EmptyParameterComponent: () => <div data-testid="widget" />,
}));
jest.mock("../components/floatComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/inputListComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/intComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/keypairListComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/mcpComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/multiselectComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/mustachePromptComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/promptComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/queryComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/sortableListComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/strRenderComponent", () => ({
  StrRenderComponent: () => <div data-testid="widget" />,
}));
jest.mock("../components/ToolsComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/toggleShadComponent", () => () => (
  <div data-testid="widget" />
));

const CONDITIONAL_SCOPES = [
  {
    scope: "Files.Read.All",
    role: "optional",
    condition: { kind: "input_truthy", input: "drive_id" },
  },
];

const connectionField = {
  type: "connection_ref",
  name: "connection",
  provider: "microsoft",
  required_scopes: ["Files.Read"],
  conditional_scopes: CONDITIONAL_SCOPES,
  capabilities: ["microsoft.files.list"],
  identity_kind: "user",
  ownership_mode: "user",
  value: "microsoft/work",
};

describe("ParameterRenderComponent - connection_ref wiring", () => {
  it("hands the picker the field's conditional scopes and the node's input values", () => {
    render(
      <ParameterRenderComponent
        handleOnNewValue={jest.fn()}
        name="connection"
        nodeId="node-1"
        templateData={connectionField}
        templateValue="microsoft/work"
        editNode={false}
        showParameter
        inspectionPanel={false}
        handleNodeClass={jest.fn()}
        nodeClass={
          {
            template: {
              _type: "Component",
              connection: connectionField,
              drive_id: { type: "str", value: "b!shared" },
              site_id: { type: "str", value: "" },
            },
          } as never
        }
        disabled={false}
      />,
    );

    expect(mockConnectionRef).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "connectionref_connection_ref_connection",
        value: "microsoft/work",
        provider: "microsoft",
        requiredScopes: ["Files.Read"],
        conditionalScopes: CONDITIONAL_SCOPES,
        inputValues: expect.objectContaining({
          drive_id: "b!shared",
          site_id: "",
          connection: "microsoft/work",
        }),
        capabilities: ["microsoft.files.list"],
        identityKind: "user",
        ownershipMode: "user",
      }),
    );
  });

  it("passes no conditional scopes for a field that declares none", () => {
    const { conditional_scopes: _omitted, ...plainField } = connectionField;
    render(
      <ParameterRenderComponent
        handleOnNewValue={jest.fn()}
        name="connection"
        nodeId="node-1"
        templateData={plainField}
        templateValue="microsoft/work"
        editNode={false}
        showParameter
        inspectionPanel={false}
        handleNodeClass={jest.fn()}
        nodeClass={{ template: { connection: plainField } } as never}
        disabled={false}
      />,
    );

    expect(mockConnectionRef).toHaveBeenLastCalledWith(
      expect.objectContaining({ conditionalScopes: [] }),
    );
  });
});
