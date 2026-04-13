import { render, waitFor } from "@testing-library/react";
import InputGlobalComponent from "..";

const mockUseGetGlobalVariables = jest.fn();
const mockInputComponent = jest.fn().mockReturnValue(null);

jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: () => mockUseGetGlobalVariables(),
}));

jest.mock("@/shared/components/delete-confirmation-modal", () => () => null);

jest.mock(
  "@/components/core/GlobalVariableModal/GlobalVariableModal",
  () =>
    function GlobalVariableModal({ children }: { children?: React.ReactNode }) {
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
      return null;
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
  });

  it("clears missing saved variables only after a successful settled fetch", async () => {
    mockUseGetGlobalVariables.mockReturnValue({
      data: [],
      isFetchedAfterMount: true,
      isFetching: false,
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

    it("temporarily includes an orphaned variable reference while it is being cleared", () => {
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

      expect(getRenderedOptions()).toContain("DELETED_VAR");
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
});
