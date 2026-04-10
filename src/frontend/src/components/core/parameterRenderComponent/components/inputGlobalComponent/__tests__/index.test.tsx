import { render, waitFor } from "@testing-library/react";
import InputGlobalComponent from "..";

const mockUseGetGlobalVariables = jest.fn();

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
    default: () => null,
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
});
