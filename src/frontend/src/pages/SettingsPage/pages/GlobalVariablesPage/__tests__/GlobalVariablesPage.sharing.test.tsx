import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import type { GlobalVariable } from "@/types/global_variables";
import GlobalVariablesPage from "../index";

const mockOpenShareDialog = jest.fn();
let mockCanShare = true;
const mockVariables: GlobalVariable[] = [
  {
    id: "variable-1",
    name: "TEST_VARIABLE",
    value: "value",
    type: "Generic",
    default_fields: [],
    is_owner: true,
  },
];

jest.mock("@/contexts/permissionsContext", () => ({
  PermissionsProvider: ({ children }: { children: ReactNode }) => children,
  usePermissions: () => ({
    can: () => true,
    isLoading: false,
    isError: false,
    permissions: { "variable-1": ["read", "write", "delete"] },
  }),
}));

jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: () => ({ data: mockVariables }),
  useDeleteGlobalVariables: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/components/core/dropdownComponent", () => ({
  __esModule: true,
  default: ({ children }: { children?: ReactNode }) => children ?? null,
}));

jest.mock("@/components/core/GlobalVariableModal/GlobalVariableModal", () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) =>
    open ? <div role="dialog" aria-label="Edit variable" /> : null,
}));

jest.mock("@/customization/components/custom-variable-share-action", () => ({
  __esModule: true,
  default: ({ resourceId }: { resourceId: string }) => (
    <button
      type="button"
      disabled={!mockCanShare}
      onClick={(event) => {
        event.stopPropagation();
        mockOpenShareDialog(resourceId);
      }}
    >
      <span aria-hidden="true">Share icon</span>
      Share variable
    </button>
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
  ForwardedIconComponent: () => null,
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({ setErrorData: jest.fn() }),
}));

describe("GlobalVariablesPage sharing in AG Grid", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCanShare = true;
    // Give the real grid a viewport in jsdom so it renders the actions column.
    jest
      .spyOn(HTMLElement.prototype, "clientWidth", "get")
      .mockReturnValue(1000);
    jest
      .spyOn(HTMLElement.prototype, "clientHeight", "get")
      .mockReturnValue(300);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it.each(["button", "icon"])(
    "opens sharing on a %s click without opening the variable editor",
    async (target) => {
      const user = userEvent.setup();
      render(<GlobalVariablesPage />);
      const action = await screen.findByRole("button", {
        name: "Share variable",
      });

      await user.click(
        target === "button" ? action : screen.getByText("Share icon"),
      );

      expect(mockOpenShareDialog).toHaveBeenCalledTimes(1);
      expect(mockOpenShareDialog).toHaveBeenCalledWith("variable-1");
      expect(
        screen.queryByRole("dialog", { name: "Edit variable" }),
      ).toBeNull();
    },
  );

  it.each(["{Enter}", " "])(
    "lets the share button handle %s without editing or selecting its row",
    async (key) => {
      const user = userEvent.setup();
      render(<GlobalVariablesPage />);
      const action = await screen.findByRole("button", {
        name: "Share variable",
      });
      action.focus();

      await user.keyboard(key);

      expect(mockOpenShareDialog).toHaveBeenCalledTimes(1);
      expect(mockOpenShareDialog).toHaveBeenCalledWith("variable-1");
      expect(
        screen.queryByRole("dialog", { name: "Edit variable" }),
      ).toBeNull();
      expect(action.closest('[role="row"]')).toHaveAttribute(
        "aria-selected",
        "false",
      );
    },
  );

  it("does not edit when clicking an empty area of the actions cell", async () => {
    const user = userEvent.setup();
    render(<GlobalVariablesPage />);
    await screen.findByRole("button", { name: "Share variable" });

    await user.click(screen.getByRole("gridcell", { name: /Share variable/ }));

    expect(mockOpenShareDialog).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog", { name: "Edit variable" })).toBeNull();
  });

  it("does not share or edit when the share action is disabled", async () => {
    mockCanShare = false;
    const user = userEvent.setup();
    render(<GlobalVariablesPage />);

    await user.click(
      await screen.findByRole("button", { name: "Share variable" }),
    );

    expect(mockOpenShareDialog).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog", { name: "Edit variable" })).toBeNull();
  });

  it.each(["click", "Enter"])(
    "still edits a data cell on %s",
    async (activation) => {
      const user = userEvent.setup();
      render(<GlobalVariablesPage />);
      const cell = await screen.findByRole("gridcell", {
        name: /TEST_VARIABLE/,
      });

      if (activation === "click") {
        await user.click(cell);
      } else {
        cell.focus();
        await user.keyboard("{Enter}");
      }

      expect(
        await screen.findByRole("dialog", { name: "Edit variable" }),
      ).toBeInTheDocument();
      expect(mockOpenShareDialog).not.toHaveBeenCalled();
    },
  );

  it("still selects a data row with Space", async () => {
    const user = userEvent.setup();
    render(<GlobalVariablesPage />);
    const cell = await screen.findByRole("gridcell", { name: /TEST_VARIABLE/ });
    cell.focus();

    await user.keyboard(" ");

    await waitFor(() => {
      expect(cell.closest('[role="row"]')).toHaveAttribute(
        "aria-selected",
        "true",
      );
    });
    expect(screen.queryByRole("dialog", { name: "Edit variable" })).toBeNull();
    expect(mockOpenShareDialog).not.toHaveBeenCalled();
  });
});
