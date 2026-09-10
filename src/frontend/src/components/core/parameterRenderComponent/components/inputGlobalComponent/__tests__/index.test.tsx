import { render, waitFor } from "@testing-library/react";
import InputGlobalComponent from "..";

const mockUseGetGlobalVariables = jest.fn();
const mockInputComponent = jest.fn().mockReturnValue(null);
const mockDeleteConfirmation = jest.fn();
const mockGlobalVariableModal = jest.fn();
let mockCurrentFlowId = "flow-project-a";

jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: (...args: unknown[]) =>
    mockUseGetGlobalVariables(...args),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: { currentFlowId: string }) => unknown) =>
    selector({ currentFlowId: mockCurrentFlowId }),
}));

jest.mock(
  "@/components/core/globalVariableDeleteConfirmation",
  () => (props: Record<string, unknown>) => {
    mockDeleteConfirmation(props);
    return null;
  },
);

jest.mock(
  "@/components/core/GlobalVariableModal/GlobalVariableModal",
  () =>
    function GlobalVariableModal({
      children,
      ...props
    }: {
      children?: React.ReactNode;
      providerScope?: { flowId?: string };
    }) {
      mockGlobalVariableModal(props);
      return <>{children}</>;
    },
);

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/components/ui/command", () => ({
  CommandItem: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

jest.mock(
  "@/components/core/parameterRenderComponent/components/inputComponent",
  () => ({
    __esModule: true,
    default: (props: Record<string, unknown>) => {
      mockInputComponent(props);
      const optionButton = props.optionButton as
        | ((option: string) => React.ReactNode)
        | undefined;
      return (
        <>
          {props.optionsButton as React.ReactNode}
          {optionButton?.("PROJECT_ONLY")}
        </>
      );
    },
  }),
);

describe("InputGlobalComponent", () => {
  const handleOnNewValue = jest.fn();

  const renderComponent = () =>
    render(
      <InputGlobalComponent
        id="global-var-input"
        value="MISSING_VAR"
        display_name="API Key"
        handleOnNewValue={handleOnNewValue}
        load_from_db
        password={false}
        editNode={false}
        disabled={false}
      />,
    );

  beforeEach(() => {
    jest.clearAllMocks();
    mockCurrentFlowId = "flow-project-a";
  });

  it("loads variables in the trusted flow scope and preserves a project-only reference", async () => {
    mockUseGetGlobalVariables.mockReturnValue({
      data: [{ id: "project-var", name: "PROJECT_ONLY" }],
      isFetchedAfterMount: true,
      isFetching: false,
      fetchStatus: "idle",
      isSuccess: true,
    });

    render(
      <InputGlobalComponent
        id="project-variable"
        value="PROJECT_ONLY"
        display_name="API Key"
        handleOnNewValue={handleOnNewValue}
        load_from_db
        password
        editNode={false}
        disabled={false}
      />,
    );

    expect(mockUseGetGlobalVariables).toHaveBeenCalledWith({
      flowId: "flow-project-a",
      enabled: true,
    });
    expect(mockGlobalVariableModal).toHaveBeenCalledWith(
      expect.objectContaining({ providerScope: { flowId: "flow-project-a" } }),
    );
    expect(mockDeleteConfirmation).toHaveBeenCalledWith(
      expect.objectContaining({
        providerScope: { flowId: "flow-project-a" },
        variableId: "project-var",
      }),
    );
    expect(mockInputComponent).toHaveBeenLastCalledWith(
      expect.objectContaining({
        value: "PROJECT_ONLY",
        options: ["PROJECT_ONLY"],
        selectedOption: "PROJECT_ONLY",
      }),
    );
    await waitFor(() => expect(handleOnNewValue).not.toHaveBeenCalled());
  });

  it("clears missing saved variables only after a successful settled fetch", async () => {
    mockUseGetGlobalVariables.mockReturnValue({
      data: [],
      isFetchedAfterMount: true,
      isFetching: false,
      fetchStatus: "idle",
      isSuccess: true,
    });

    renderComponent();

    await waitFor(() => {
      expect(handleOnNewValue).toHaveBeenCalledWith(
        { value: "", load_from_db: false },
        { skipSnapshot: true },
      );
    });
  });

  it("clears a missing saved variable exactly once when other variables exist", async () => {
    mockUseGetGlobalVariables.mockReturnValue({
      data: [{ name: "OTHER_VAR" }],
      isFetchedAfterMount: true,
      isFetching: false,
      fetchStatus: "idle",
      isSuccess: true,
    });

    renderComponent();

    await waitFor(() => expect(handleOnNewValue).toHaveBeenCalledTimes(1));
    expect(handleOnNewValue).toHaveBeenCalledWith(
      { value: "", load_from_db: false },
      { skipSnapshot: true },
    );
  });

  it("does not clear while a background refetch is still in flight", async () => {
    mockUseGetGlobalVariables.mockReturnValue({
      data: [{ name: "OTHER_VAR" }],
      isFetchedAfterMount: false,
      isFetching: true,
      isSuccess: true,
    });

    renderComponent();

    await waitFor(() => {
      expect(handleOnNewValue).not.toHaveBeenCalled();
    });
    expect(mockInputComponent).toHaveBeenLastCalledWith(
      expect.objectContaining({
        value: "",
        options: [],
        selectedOption: "",
      }),
    );

    const staleSelect = mockInputComponent.mock.calls[0][0]
      .setSelectedOption as (value: string) => void;
    staleSelect("OTHER_VAR");
    expect(handleOnNewValue).not.toHaveBeenCalled();
  });

  it("hides cached credentials while an offline policy refresh is paused", async () => {
    mockUseGetGlobalVariables.mockReturnValue({
      data: [{ name: "MISSING_VAR" }],
      isFetchedAfterMount: true,
      isFetching: false,
      fetchStatus: "paused",
      isSuccess: true,
    });

    renderComponent();

    await waitFor(() => expect(handleOnNewValue).not.toHaveBeenCalled());
    expect(mockInputComponent).toHaveBeenLastCalledWith(
      expect.objectContaining({
        value: "",
        options: [],
        selectedOption: "",
      }),
    );
  });

  it("does not clear when the global variables query fails", async () => {
    mockUseGetGlobalVariables.mockReturnValue({
      data: undefined,
      isFetchedAfterMount: true,
      isFetching: false,
      isSuccess: false,
    });

    renderComponent();

    await waitFor(() => {
      expect(handleOnNewValue).not.toHaveBeenCalled();
    });
    expect(mockInputComponent).toHaveBeenLastCalledWith(
      expect.objectContaining({
        value: "",
        options: [],
        selectedOption: "",
      }),
    );
  });

  it("shows settled scoped data supplied by another observer after this component remounts", async () => {
    mockUseGetGlobalVariables.mockReturnValue({
      data: [{ name: "NEW_SCOPED_VAR" }],
      isFetchedAfterMount: false,
      isFetching: false,
      fetchStatus: "idle",
      isSuccess: true,
    });

    render(
      <InputGlobalComponent
        id="new-scoped-variable"
        value=""
        display_name="API Key"
        handleOnNewValue={handleOnNewValue}
        load_from_db={false}
        password
        editNode={false}
        disabled={false}
      />,
    );

    expect(mockInputComponent).toHaveBeenLastCalledWith(
      expect.objectContaining({ options: ["NEW_SCOPED_VAR"] }),
    );

    const selectOption = mockInputComponent.mock.calls[0][0]
      .setSelectedOption as (value: string) => void;
    selectOption("NEW_SCOPED_VAR");
    expect(handleOnNewValue).toHaveBeenCalledWith({
      value: "NEW_SCOPED_VAR",
      load_from_db: true,
    });
  });

  it("does not clear a cached saved reference until this mount has fetched its scope", async () => {
    mockUseGetGlobalVariables.mockReturnValue({
      data: [{ name: "OTHER_VAR" }],
      isFetchedAfterMount: false,
      isFetching: false,
      fetchStatus: "idle",
      isSuccess: true,
    });

    const { rerender } = renderComponent();

    await waitFor(() => {
      expect(handleOnNewValue).not.toHaveBeenCalled();
    });
    expect(mockInputComponent).toHaveBeenLastCalledWith(
      expect.objectContaining({
        value: "",
        options: ["OTHER_VAR"],
        selectedOption: "",
      }),
    );

    mockUseGetGlobalVariables.mockReturnValue({
      data: [{ name: "OTHER_VAR" }],
      isFetchedAfterMount: true,
      isFetching: false,
      fetchStatus: "idle",
      isSuccess: true,
    });
    rerender(
      <InputGlobalComponent
        id="global-var-input"
        value="MISSING_VAR"
        display_name="API Key"
        handleOnNewValue={handleOnNewValue}
        load_from_db
        password={false}
        editNode={false}
        disabled={false}
      />,
    );

    await waitFor(() => expect(handleOnNewValue).toHaveBeenCalledTimes(1));
    expect(handleOnNewValue).toHaveBeenCalledWith(
      { value: "", load_from_db: false },
      { skipSnapshot: true },
    );
  });

  it("forwards ariaLabelledBy through to the underlying InputComponent", () => {
    mockUseGetGlobalVariables.mockReturnValue({
      data: [],
      isFetchedAfterMount: true,
      isFetching: false,
      fetchStatus: "idle",
      isSuccess: true,
    });

    render(
      <InputGlobalComponent
        id="test"
        value=""
        display_name="API Key"
        handleOnNewValue={handleOnNewValue}
        load_from_db={false}
        password={false}
        editNode={false}
        disabled={false}
        ariaLabelledBy="field-label-id"
      />,
    );

    expect(mockInputComponent).toHaveBeenCalledWith(
      expect.objectContaining({ ariaLabelledBy: "field-label-id" }),
    );
  });

  describe("options passed to InputComponent", () => {
    const configuredVariables = [
      { name: "MY_API_KEY" },
      { name: "ANOTHER_VAR" },
    ];

    beforeEach(() => {
      mockUseGetGlobalVariables.mockReturnValue({
        data: configuredVariables,
        isFetchedAfterMount: true,
        isFetching: false,
        fetchStatus: "idle",
        isSuccess: true,
      });
    });

    const getRenderedOptions = (): string[] =>
      mockInputComponent.mock.calls[mockInputComponent.mock.calls.length - 1][0]
        .options as string[];

    it("does not add typed camelCase text to the dropdown", () => {
      render(
        <InputGlobalComponent
          id="test"
          value="invalidKey"
          display_name="API Key"
          handleOnNewValue={handleOnNewValue}
          load_from_db={false}
          password={true}
          editNode={false}
          disabled={false}
        />,
      );

      expect(getRenderedOptions()).not.toContain("invalidKey");
      expect(getRenderedOptions()).toEqual(["MY_API_KEY", "ANOTHER_VAR"]);
    });

    it("does not add SCREAMING_SNAKE_CASE typed text to the dropdown", () => {
      render(
        <InputGlobalComponent
          id="test"
          value="OPENAI_API_KEY"
          display_name="API Key"
          handleOnNewValue={handleOnNewValue}
          load_from_db={false}
          password={true}
          editNode={false}
          disabled={false}
        />,
      );

      expect(getRenderedOptions()).not.toContain("OPENAI_API_KEY");
      expect(getRenderedOptions()).toEqual(["MY_API_KEY", "ANOTHER_VAR"]);
    });

    it("shows only configured global variables when the field is not a password field", () => {
      render(
        <InputGlobalComponent
          id="test"
          value="SOME_TYPED_VALUE"
          display_name="Some Field"
          handleOnNewValue={handleOnNewValue}
          load_from_db={false}
          password={false}
          editNode={false}
          disabled={false}
        />,
      );

      expect(getRenderedOptions()).toEqual(["MY_API_KEY", "ANOTHER_VAR"]);
    });

    it("does not present an orphaned saved reference while it is being cleared", () => {
      render(
        <InputGlobalComponent
          id="test"
          value="DELETED_VAR"
          display_name="API Key"
          handleOnNewValue={handleOnNewValue}
          load_from_db={true}
          password={false}
          editNode={false}
          disabled={false}
        />,
      );

      expect(getRenderedOptions()).not.toContain("DELETED_VAR");
      expect(mockInputComponent).toHaveBeenLastCalledWith(
        expect.objectContaining({ value: "", selectedOption: "" }),
      );
    });

    it("does not duplicate a variable that already exists in the configured list", () => {
      render(
        <InputGlobalComponent
          id="test"
          value="MY_API_KEY"
          display_name="API Key"
          handleOnNewValue={handleOnNewValue}
          load_from_db={true}
          password={false}
          editNode={false}
          disabled={false}
        />,
      );

      const options = getRenderedOptions();
      expect(options.filter((o) => o === "MY_API_KEY")).toHaveLength(1);
    });
  });

  describe("disabledOptions for Credential-typed variables", () => {
    const variables = [
      { name: "MY_GENERIC_VAR", type: "Generic" },
      { name: "MY_CREDENTIAL", type: "Credential" },
      { name: "ANOTHER_CREDENTIAL", type: "Credential" },
    ];

    beforeEach(() => {
      mockUseGetGlobalVariables.mockReturnValue({
        data: variables,
        isFetchedAfterMount: true,
        isFetching: false,
        fetchStatus: "idle",
        isSuccess: true,
      });
    });

    const getRenderedDisabledOptions = (): Record<string, string> | undefined =>
      mockInputComponent.mock.calls[mockInputComponent.mock.calls.length - 1][0]
        .disabledOptions as Record<string, string> | undefined;

    it("disables Credential-typed variables when field is non-secret (no _input_type, password=false)", () => {
      render(
        <InputGlobalComponent
          id="test"
          value=""
          display_name="Some Field"
          handleOnNewValue={handleOnNewValue}
          load_from_db={false}
          password={false}
          editNode={false}
          disabled={false}
        />,
      );

      const disabledOptions = getRenderedDisabledOptions() ?? {};
      expect(Object.keys(disabledOptions).sort()).toEqual([
        "ANOTHER_CREDENTIAL",
        "MY_CREDENTIAL",
      ]);
      expect(disabledOptions.MY_CREDENTIAL).toMatch(/secret fields/i);
      expect(disabledOptions.MY_GENERIC_VAR).toBeUndefined();
    });

    it("does not disable any options for SecretStrInput", () => {
      render(
        <InputGlobalComponent
          id="test"
          value=""
          display_name="API Key"
          handleOnNewValue={handleOnNewValue}
          load_from_db={false}
          password={true}
          _input_type="SecretStrInput"
          editNode={false}
          disabled={false}
        />,
      );

      expect(getRenderedDisabledOptions()).toEqual({});
    });

    it("does not disable any options for MultilineSecretInput", () => {
      render(
        <InputGlobalComponent
          id="test"
          value=""
          display_name="Token"
          handleOnNewValue={handleOnNewValue}
          load_from_db={false}
          password={true}
          _input_type="MultilineSecretInput"
          editNode={false}
          disabled={false}
        />,
      );

      expect(getRenderedDisabledOptions()).toEqual({});
    });

    it("disables credentials for MultilineInput even when password=true (use_global_variable toggle case)", () => {
      // TextInput's "Use Global Variable" toggle flips password=true on a
      // MultilineInput field for display masking. The intrinsic type is still
      // non-secret, so credentials must remain disabled.
      render(
        <InputGlobalComponent
          id="test"
          value=""
          display_name="Text"
          handleOnNewValue={handleOnNewValue}
          load_from_db={false}
          password={true}
          _input_type="MultilineInput"
          editNode={false}
          disabled={false}
        />,
      );

      const disabledOptions = getRenderedDisabledOptions() ?? {};
      expect(Object.keys(disabledOptions).sort()).toEqual([
        "ANOTHER_CREDENTIAL",
        "MY_CREDENTIAL",
      ]);
      expect(disabledOptions.MY_GENERIC_VAR).toBeUndefined();
    });

    it("falls back to password flag when _input_type is missing", () => {
      render(
        <InputGlobalComponent
          id="test"
          value=""
          display_name="Legacy"
          handleOnNewValue={handleOnNewValue}
          load_from_db={false}
          password={true}
          editNode={false}
          disabled={false}
        />,
      );

      // No _input_type → fall back to password=true → secret field → no disabling.
      expect(getRenderedDisabledOptions()).toEqual({});
    });
  });
});
