import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryDetailsHeader } from "../MemoryDetailsHeader";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span>{name}</span>,
}));

jest.mock("@/components/ui/switch", () => ({
  Switch: ({ onCheckedChange, checked }: any) => (
    <input
      type="checkbox"
      aria-label="auto-capture"
      checked={checked}
      onChange={(e) => onCheckedChange(e.target.checked)}
    />
  ),
}));

jest.mock("@/modals/deleteConfirmationModal", () => ({
  __esModule: true,
  default: ({ children, onConfirm }: any) => (
    <div>
      {children}
      <button onClick={() => onConfirm({ stopPropagation: jest.fn() })}>
        confirm-delete
      </button>
    </div>
  ),
}));

describe("MemoryDetailsHeader", () => {
  const makeProps = (overrides: Partial<any> = {}) =>
    ({
      memory: {
        id: "m1",
        name: "Memory One",
        description: "desc",
        status: "idle",
        is_active: true,
      },
      isProcessing: false,
      manualUpdateMutation: { mutate: jest.fn(), isPending: false },
      handleManualUpdate: jest.fn(),
      deleteMutation: { mutate: jest.fn(), isPending: false },
      updateMemoryMutation: { isPending: false },
      handleToggleActive: jest.fn(),
      ...overrides,
    }) as any;

  it("renders memory information", () => {
    const props = makeProps();
    render(<MemoryDetailsHeader {...props} />);
    expect(screen.getByText("Memory One")).toBeInTheDocument();
    expect(screen.getByText("Auto-capture on")).toBeInTheDocument();
  });

  it("calls mutate handlers for actions", () => {
    const props = makeProps();
    render(<MemoryDetailsHeader {...props} />);

    fireEvent.click(screen.getByText("confirm-delete"));
    expect(props.deleteMutation.mutate).toHaveBeenCalledWith({
      memoryId: "m1",
    });
  });

  it("toggles auto-capture", () => {
    const props = makeProps();
    render(<MemoryDetailsHeader {...props} />);
    fireEvent.click(screen.getByLabelText("auto-capture"));
    expect(props.handleToggleActive).toHaveBeenCalled();
  });
});
