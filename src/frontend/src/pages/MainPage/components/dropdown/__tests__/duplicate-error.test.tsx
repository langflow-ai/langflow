import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { FlowType } from "@/types/flow";
import DropdownComponent from "../index";

const mockHandleDuplicate = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();

jest.mock("../../../hooks/use-handle-duplicate", () => ({
  __esModule: true,
  default: () => ({ handleDuplicate: mockHandleDuplicate }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector) =>
    selector({
      setErrorData: mockSetErrorData,
      setSuccessData: mockSetSuccessData,
    }),
}));

jest.mock("@/customization/components/custom-flow-share-action", () => ({
  __esModule: true,
  default: () => null,
}));

const renderMenu = () =>
  render(
    <DropdownMenu open>
      <DropdownMenuTrigger>Flow actions</DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownComponent
          flowData={{ id: "legacy-flow", is_component: false } as FlowType}
          setOpenDelete={jest.fn()}
          handleExport={jest.fn()}
          handleEdit={jest.fn()}
        />
      </DropdownMenuContent>
    </DropdownMenu>,
  );

describe("flow duplication errors", () => {
  beforeEach(() => jest.clearAllMocks());

  it("shows one actionable alert when duplicating a legacy flow is refused", async () => {
    const message =
      "A flow can have only one trigger. Remove the extra triggers and try again.";
    mockHandleDuplicate.mockRejectedValueOnce({
      response: {
        status: 422,
        data: {
          detail: [
            { msg: `Value error, ${message}` },
            { msg: `Value error, ${message}` },
          ],
        },
      },
    });
    renderMenu();

    await userEvent.click(screen.getByRole("menuitem", { name: "Duplicate" }));

    await waitFor(() => expect(mockSetErrorData).toHaveBeenCalledTimes(1));
    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Could not duplicate the flow",
      list: [message],
    });
    expect(mockSetSuccessData).not.toHaveBeenCalled();
  });

  it("reports success when duplication finishes", async () => {
    mockHandleDuplicate.mockResolvedValueOnce(undefined);
    renderMenu();

    await userEvent.click(screen.getByRole("menuitem", { name: "Duplicate" }));

    await waitFor(() => expect(mockSetSuccessData).toHaveBeenCalledTimes(1));
    expect(mockSetErrorData).not.toHaveBeenCalled();
  });
});
