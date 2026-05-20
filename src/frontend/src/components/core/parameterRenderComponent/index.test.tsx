import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import type { APIClassType } from "@/types/api";
import { ParameterRenderComponent } from ".";

let mockCloudOnly = false;
let mockTemplates: Record<string, unknown> = {};
type CloudModeState = {
  cloudOnly: boolean;
  setCloudOnly: jest.Mock;
};
type TypesStoreState = {
  templates: Record<string, unknown>;
};
type StrRenderProps = {
  value?: string | number | readonly string[] | null;
  placeholder?: string | null;
};
type SortableListRenderProps = {
  value?: Array<{ name?: string }>;
  options?: Array<{ name?: string }>;
  cloudIncompatibleOptions?: unknown[];
};

jest.mock("@/stores/cloudModeStore", () => ({
  useCloudModeStore: <T,>(selector: (state: CloudModeState) => T) =>
    selector({ cloudOnly: mockCloudOnly, setCloudOnly: jest.fn() }),
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: <T,>(selector: (state: TypesStoreState) => T) =>
    selector({ templates: mockTemplates }),
}));

jest.mock("./components/strRenderComponent", () => ({
  StrRenderComponent: ({ value, placeholder }: StrRenderProps) => (
    <div
      data-testid="str-render-props"
      data-value={value ?? ""}
      data-placeholder={placeholder ?? ""}
    />
  ),
}));

jest.mock("./components/mcpComponent", () => () => (
  <div data-testid="mcp-component" />
));

jest.mock("./components/sortableListComponent", () => ({
  __esModule: true,
  default: ({
    value = [],
    options = [],
    cloudIncompatibleOptions = [],
  }: SortableListRenderProps) => (
    <div
      data-testid="sortable-list-props"
      data-value={value.map((option) => option.name ?? "").join(",")}
      data-options={options.map((option) => option.name ?? "").join(",")}
      data-cloud-incompatible={cloudIncompatibleOptions.join(",")}
    />
  ),
}));

describe("ParameterRenderComponent", () => {
  beforeEach(() => {
    mockCloudOnly = false;
    mockTemplates = {};
  });

  const createNodeClass = (
    overrides: Record<string, unknown> = {},
  ): APIClassType =>
    ({
      description: "Test component",
      template: {},
      display_name: "Test Component",
      documentation: "Test component documentation",
      ...overrides,
    }) as APIClassType;

  const baseProps: ComponentProps<typeof ParameterRenderComponent> = {
    handleOnNewValue: jest.fn(),
    name: "url",
    nodeId: "test-node-id",
    editNode: true,
    showParameter: true,
    inspectionPanel: false,
    handleNodeClass: jest.fn(),
    templateValue: "",
    nodeClass: createNodeClass({
      metadata: {
        cloud_default_overrides: {
          url: {
            value: "",
            placeholder: "Enter your cloud URL",
          },
        },
      },
    }),
    disabled: false,
    templateData: { type: "str", name: "url", placeholder: "Local URL" },
  };

  it("keeps an existing saved value visible in cloud mode", () => {
    mockCloudOnly = true;

    render(
      <ParameterRenderComponent
        {...baseProps}
        templateValue="https://prod.example.com"
      />,
    );

    const renderedProps = screen.getByTestId("str-render-props");
    expect(renderedProps).toHaveAttribute(
      "data-value",
      "https://prod.example.com",
    );
    expect(renderedProps).toHaveAttribute("data-placeholder", "Local URL");
  });

  it("uses the cloud placeholder when a new value is empty", () => {
    mockCloudOnly = true;

    render(<ParameterRenderComponent {...baseProps} templateValue="" />);

    const renderedProps = screen.getByTestId("str-render-props");
    expect(renderedProps).toHaveAttribute("data-value", "");
    expect(renderedProps).toHaveAttribute(
      "data-placeholder",
      "Enter your cloud URL",
    );
  });

  it("backfills the cloud placeholder from the current catalog for older saved nodes", () => {
    mockCloudOnly = true;
    mockTemplates = {
      File: createNodeClass({
        display_name: "Read File",
        documentation: "",
        metadata: {
          cloud_default_overrides: {
            url: {
              placeholder: "Enter your cloud URL",
            },
          },
        },
      }),
    };

    render(
      <ParameterRenderComponent
        {...baseProps}
        nodeType="File"
        nodeClass={createNodeClass()}
        templateValue=""
      />,
    );

    const renderedProps = screen.getByTestId("str-render-props");
    expect(renderedProps).toHaveAttribute(
      "data-placeholder",
      "Enter your cloud URL",
    );
  });

  it("preserves incompatible sortable values while filtering them from the chooser in cloud mode", () => {
    mockCloudOnly = true;

    render(
      <ParameterRenderComponent
        {...baseProps}
        name="storage_location"
        templateValue={[{ name: "Local" }]}
        templateData={{
          type: "sortableList",
          name: "storage_location",
          options: [{ name: "Local" }, { name: "AWS" }],
          limit: 1,
        }}
        nodeClass={createNodeClass({
          metadata: {
            cloud_incompatible_options: {
              storage_location: ["Local"],
            },
          },
        })}
      />,
    );

    const renderedProps = screen.getByTestId("sortable-list-props");
    expect(renderedProps).toHaveAttribute("data-value", "Local");
    expect(renderedProps).toHaveAttribute("data-options", "AWS");
    expect(renderedProps).toHaveAttribute("data-cloud-incompatible", "Local");
  });

  it("backfills cloud-incompatible sortable options from the current catalog for older saved nodes", () => {
    mockCloudOnly = true;
    mockTemplates = {
      File: createNodeClass({
        display_name: "Read File",
        documentation: "",
        metadata: {
          cloud_incompatible_options: {
            storage_location: ["Local"],
          },
        },
      }),
    };

    render(
      <ParameterRenderComponent
        {...baseProps}
        nodeType="File"
        name="storage_location"
        templateValue={[{ name: "Local" }]}
        templateData={{
          type: "sortableList",
          name: "storage_location",
          options: [{ name: "Local" }, { name: "AWS" }],
          limit: 1,
        }}
        nodeClass={createNodeClass()}
      />,
    );

    const renderedProps = screen.getByTestId("sortable-list-props");
    expect(renderedProps).toHaveAttribute("data-value", "Local");
    expect(renderedProps).toHaveAttribute("data-options", "AWS");
    expect(renderedProps).toHaveAttribute("data-cloud-incompatible", "Local");
  });
});
