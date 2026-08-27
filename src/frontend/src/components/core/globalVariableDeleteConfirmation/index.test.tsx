import { fireEvent, render, screen } from "@testing-library/react";
import GlobalVariableDeleteConfirmation from ".";

const mockDeleteVariable = jest.fn();
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
    selector({ setErrorData: jest.fn() }),
}));

jest.mock("react-i18next", () => ({
  ...jest.requireActual("react-i18next"),
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe("GlobalVariableDeleteConfirmation provider scope", () => {
  it("reads and deletes the variable in the same flow scope", () => {
    const providerScope = { flowId: "flow-project-a" };
    render(
      <GlobalVariableDeleteConfirmation
        option="PROJECT_KEY"
        onConfirmDelete={jest.fn()}
        providerScope={providerScope}
      />,
    );

    expect(mockUseGetGlobalVariables).toHaveBeenCalledWith(providerScope);
    fireEvent.click(screen.getByTestId("confirm-delete"));
    expect(mockDeleteVariable).toHaveBeenCalledWith(
      { id: "var-project", ...providerScope },
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      }),
    );
  });
});
