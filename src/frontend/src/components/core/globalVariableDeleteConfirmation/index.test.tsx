import { fireEvent, render, screen } from "@testing-library/react";
import GlobalVariableDeleteConfirmation from ".";

const mockDeleteVariable = jest.fn();
const mockSetErrorData = jest.fn();
const mockUseGetGlobalVariables = jest.fn((_options?: unknown) => ({
  data: [{ id: "var-project", name: "PROJECT_KEY" }],
}));

jest.mock("@/controllers/API/queries/variables", () => ({
  useDeleteGlobalVariables: () => ({ mutate: mockDeleteVariable }),
  useGetGlobalVariables: (options?: unknown) =>
    mockUseGetGlobalVariables(options),
}));

jest.mock("@/modals/deleteConfirmationModal", () => ({
  __esModule: true,
  default: ({
    children,
    onConfirm,
  }: {
    children: React.ReactNode;
    onConfirm: (event: React.MouseEvent<HTMLButtonElement>) => void;
  }) => (
    <div>
      {children}
      <button type="button" data-testid="confirm-delete" onClick={onConfirm}>
        Confirm
      </button>
    </div>
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: string[]) => classes.filter(Boolean).join(" "),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: { setErrorData: jest.Mock }) => unknown) =>
    selector({ setErrorData: mockSetErrorData }),
}));

jest.mock("react-i18next", () => ({
  ...jest.requireActual("react-i18next"),
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe("GlobalVariableDeleteConfirmation provider scope", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("deletes the parent-resolved variable id without starting a nested read", () => {
    const providerScope = { flowId: "flow-project-a" };
    render(
      <GlobalVariableDeleteConfirmation
        option="PROJECT_KEY"
        variableId="var-project"
        onConfirmDelete={jest.fn()}
        providerScope={providerScope}
      />,
    );

    expect(mockUseGetGlobalVariables).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("confirm-delete"));
    expect(mockDeleteVariable).toHaveBeenCalledWith(
      { id: "var-project", ...providerScope },
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      }),
    );
  });

  it("reports the option name when the parent cannot resolve an id", () => {
    render(
      <GlobalVariableDeleteConfirmation
        option="MISSING_KEY"
        onConfirmDelete={jest.fn()}
        providerScope={{ flowId: "flow-project-a" }}
      />,
    );

    fireEvent.click(screen.getByTestId("confirm-delete"));

    expect(mockDeleteVariable).not.toHaveBeenCalled();
    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "globalVars.errorDeletingVariable",
      list: ["globalVars.errorIdNotFound"],
    });
  });

  it("reports the option name when the scoped delete is rejected", () => {
    render(
      <GlobalVariableDeleteConfirmation
        option="PROJECT_KEY"
        variableId="var-project"
        onConfirmDelete={jest.fn()}
        providerScope={{ flowId: "flow-project-a" }}
      />,
    );

    fireEvent.click(screen.getByTestId("confirm-delete"));
    const mutationOptions = mockDeleteVariable.mock.calls[0][1];
    mutationOptions.onError();

    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "globalVars.errorDeletingVariable",
      list: ["globalVars.errorIdNotFound"],
    });
  });
});
