import { act, render, waitFor } from "@testing-library/react";
import { StrRenderComponent } from "..";

// ── child component mocks ────────────────────────────────────────────────────

const mockInputGlobalComponent = jest.fn().mockReturnValue(null);
const mockInputComponent = jest.fn().mockReturnValue(null);
const mockTextAreaComponent = jest.fn().mockReturnValue(null);
const mockDropdownComponent = jest.fn().mockReturnValue(null);
const mockWebhookFieldComponent = jest.fn().mockReturnValue(null);
const mockCopyFieldAreaComponent = jest.fn().mockReturnValue(null);

jest.mock(
  "@/components/core/parameterRenderComponent/components/inputGlobalComponent",
  () => ({
    __esModule: true,
    default: (props: Record<string, unknown>) => {
      mockInputGlobalComponent(props);
      return null;
    },
  }),
);

jest.mock(
  "@/components/core/parameterRenderComponent/components/inputComponent",
  () => ({
    __esModule: true,
    default: (props: Record<string, unknown>) => {
      mockInputComponent(props);
      return null;
    },
  }),
);

jest.mock(
  "@/components/core/parameterRenderComponent/components/textAreaComponent",
  () => ({
    __esModule: true,
    default: (props: Record<string, unknown>) => {
      mockTextAreaComponent(props);
      return null;
    },
  }),
);

jest.mock(
  "@/components/core/parameterRenderComponent/components/dropdownComponent",
  () => ({
    __esModule: true,
    default: (props: Record<string, unknown>) => {
      mockDropdownComponent(props);
      return null;
    },
  }),
);

jest.mock(
  "@/components/core/parameterRenderComponent/components/webhookFieldComponent",
  () => ({
    __esModule: true,
    default: (props: Record<string, unknown>) => {
      mockWebhookFieldComponent(props);
      return null;
    },
  }),
);

jest.mock(
  "@/components/core/parameterRenderComponent/components/copyFieldAreaComponent",
  () => ({
    __esModule: true,
    default: (props: Record<string, unknown>) => {
      mockCopyFieldAreaComponent(props);
      return null;
    },
  }),
);

// ── helpers ──────────────────────────────────────────────────────────────────

const buildTemplateData = (overrides: Record<string, unknown> = {}) => ({
  type: "str",
  password: false,
  multiline: false,
  copy_field: false,
  load_from_db: false,
  refresh_button: false,
  options: undefined,
  combobox: false,
  ...overrides,
});

const buildProps = (
  templateDataOverrides = {},
  propOverrides: Record<string, unknown> = {},
) => ({
  templateData: buildTemplateData(templateDataOverrides),
  name: "test_field",
  display_name: "Test Field",
  placeholder: "Enter value",
  nodeId: "node-1",
  nodeClass: {} as any,
  handleNodeClass: jest.fn(),
  id: "test-field-id",
  value: "",
  editNode: false,
  handleOnNewValue: jest.fn(),
  disabled: false,
  isToolMode: false,
  nodeInformationMetadata: undefined,
  ...propOverrides,
});

// ── tests ─────────────────────────────────────────────────────────────────────

describe("StrRenderComponent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ── component selection ──────────────────────────────────────────────────

  describe("component selection", () => {
    it("renders InputGlobalComponent for SecretStr type", () => {
      render(<StrRenderComponent {...buildProps({ type: "SecretStr" })} />);
      expect(mockInputGlobalComponent).toHaveBeenCalled();
      expect(mockInputComponent).not.toHaveBeenCalled();
    });

    it("renders InputGlobalComponent when password is true", () => {
      render(<StrRenderComponent {...buildProps({ password: true })} />);
      expect(mockInputGlobalComponent).toHaveBeenCalled();
      expect(mockInputComponent).not.toHaveBeenCalled();
    });

    it("renders plain InputComponent for a non-secret, non-password field", () => {
      render(<StrRenderComponent {...buildProps()} />);
      expect(mockInputComponent).toHaveBeenCalled();
      expect(mockInputGlobalComponent).not.toHaveBeenCalled();
    });

    it("renders TextAreaComponent for a multiline field", () => {
      render(<StrRenderComponent {...buildProps({ multiline: true })} />);
      expect(mockTextAreaComponent).toHaveBeenCalled();
      expect(mockInputComponent).not.toHaveBeenCalled();
    });

    it("renders WebhookFieldComponent for a multiline webhook node", () => {
      render(
        <StrRenderComponent
          {...buildProps(
            { multiline: true },
            {
              nodeInformationMetadata: {
                nodeType: "webhook",
                flowId: "flow-1",
                flowName: "Flow",
                isAuth: false,
                variableName: "",
              },
            },
          )}
        />,
      );
      expect(mockWebhookFieldComponent).toHaveBeenCalled();
      expect(mockTextAreaComponent).not.toHaveBeenCalled();
    });

    it("renders CopyFieldAreaComponent for a multiline copy_field", () => {
      render(
        <StrRenderComponent
          {...buildProps({ multiline: true, copy_field: true })}
        />,
      );
      expect(mockCopyFieldAreaComponent).toHaveBeenCalled();
      expect(mockTextAreaComponent).not.toHaveBeenCalled();
    });

    it("renders DropdownComponent when options are present", () => {
      render(
        <StrRenderComponent {...buildProps({ options: ["a", "b", "c"] })} />,
      );
      expect(mockDropdownComponent).toHaveBeenCalled();
      expect(mockInputComponent).not.toHaveBeenCalled();
    });
  });

  // ── hasRefreshButton forwarding ──────────────────────────────────────────

  describe("hasRefreshButton forwarding", () => {
    it("forwards hasRefreshButton=true to InputGlobalComponent", () => {
      render(
        <StrRenderComponent
          {...buildProps({ type: "SecretStr", refresh_button: true })}
        />,
      );
      const receivedProps = mockInputGlobalComponent.mock.calls[0][0];
      expect(receivedProps.hasRefreshButton).toBe(true);
    });

    it("forwards hasRefreshButton=false to InputGlobalComponent when refresh_button is absent", () => {
      render(
        <StrRenderComponent
          {...buildProps({ type: "SecretStr", refresh_button: false })}
        />,
      );
      const receivedProps = mockInputGlobalComponent.mock.calls[0][0];
      expect(receivedProps.hasRefreshButton).toBe(false);
    });

    it("forwards hasRefreshButton=true to plain InputComponent", () => {
      render(<StrRenderComponent {...buildProps({ refresh_button: true })} />);
      const receivedProps = mockInputComponent.mock.calls[0][0];
      expect(receivedProps.hasRefreshButton).toBe(true);
    });

    it("forwards hasRefreshButton=false to plain InputComponent when refresh_button is absent", () => {
      render(<StrRenderComponent {...buildProps({ refresh_button: false })} />);
      const receivedProps = mockInputComponent.mock.calls[0][0];
      expect(receivedProps.hasRefreshButton).toBe(false);
    });
  });

  // ── load_from_db cleanup effect ──────────────────────────────────────────

  describe("load_from_db cleanup effect", () => {
    it("clears load_from_db when the field is not a global-variable field and load_from_db is true", async () => {
      const handleOnNewValue = jest.fn();
      render(
        <StrRenderComponent
          {...buildProps(
            { type: "str", password: false, load_from_db: true },
            { handleOnNewValue },
          )}
        />,
      );

      await waitFor(() => {
        expect(handleOnNewValue).toHaveBeenCalledWith(
          { load_from_db: false },
          { skipSnapshot: true },
        );
      });
    });

    it("does not clear load_from_db for a SecretStr field", async () => {
      const handleOnNewValue = jest.fn();
      render(
        <StrRenderComponent
          {...buildProps(
            { type: "SecretStr", load_from_db: true },
            { handleOnNewValue },
          )}
        />,
      );

      // Give the effect time to potentially fire
      await act(async () => {});

      expect(handleOnNewValue).not.toHaveBeenCalled();
    });

    it("does not clear load_from_db for a password=true field", async () => {
      const handleOnNewValue = jest.fn();
      render(
        <StrRenderComponent
          {...buildProps(
            { type: "str", password: true, load_from_db: true },
            { handleOnNewValue },
          )}
        />,
      );

      await act(async () => {});

      expect(handleOnNewValue).not.toHaveBeenCalled();
    });

    it("does not call handleOnNewValue when load_from_db is already false", async () => {
      const handleOnNewValue = jest.fn();
      render(
        <StrRenderComponent
          {...buildProps(
            { type: "str", password: false, load_from_db: false },
            { handleOnNewValue },
          )}
        />,
      );

      await act(async () => {});

      expect(handleOnNewValue).not.toHaveBeenCalled();
    });
  });

  // ── InputComponent onChange behaviour ────────────────────────────────────

  describe("plain InputComponent onChange", () => {
    it("always passes load_from_db: false when the user types", () => {
      const handleOnNewValue = jest.fn();
      render(<StrRenderComponent {...buildProps({}, { handleOnNewValue })} />);

      // Extract the onChange prop forwarded to InputComponent
      const { onChange } = mockInputComponent.mock.calls[0][0] as {
        onChange: (value: string, skipSnapshot?: boolean) => void;
      };

      onChange("hello");

      expect(handleOnNewValue).toHaveBeenCalledWith(
        { value: "hello", load_from_db: false },
        { skipSnapshot: undefined },
      );
    });

    it("forwards the skipSnapshot flag through to handleOnNewValue", () => {
      const handleOnNewValue = jest.fn();
      render(<StrRenderComponent {...buildProps({}, { handleOnNewValue })} />);

      const { onChange } = mockInputComponent.mock.calls[0][0] as {
        onChange: (value: string, skipSnapshot?: boolean) => void;
      };

      onChange("world", true);

      expect(handleOnNewValue).toHaveBeenCalledWith(
        { value: "world", load_from_db: false },
        { skipSnapshot: true },
      );
    });
  });
});
