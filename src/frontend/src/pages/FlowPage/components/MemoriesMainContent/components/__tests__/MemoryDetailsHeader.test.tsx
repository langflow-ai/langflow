import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryDetailsHeader } from "../MemoryDetailsHeader";
import type { MemoryDetailsHeaderProps } from "../../types";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span>{name}</span>,
}));

jest.mock("@/components/ui/switch", () => ({
  Switch: ({ onCheckedChange, checked, "aria-label": ariaLabel }: {
    onCheckedChange: (checked: boolean) => void;
    checked: boolean;
    "aria-label"?: string;
  }) => (
    <input
      type="checkbox"
      aria-label={ariaLabel ?? "switch"}
      checked={checked}
      onChange={(e) => onCheckedChange(e.target.checked)}
    />
  ),
}));

jest.mock("@/modals/deleteConfirmationModal", () => ({
  __esModule: true,
  default: ({
    children,
    onConfirm,
  }: {
    children: React.ReactNode;
    onConfirm: (e: { stopPropagation: () => void }) => void;
  }) => (
    <div>
      {children}
      <button onClick={() => onConfirm({ stopPropagation: jest.fn() })}>
        confirm-delete
      </button>
    </div>
  ),
}));

describe("MemoryDetailsHeader", () => {
  const makeProps = (overrides?: Partial<MemoryDetailsHeaderProps>) => {
    const base: MemoryDetailsHeaderProps = {
      memory: {
        id: "m1",
        name: "Memory One",
        description: "desc",
        status: "idle",
        is_active: true,
      } as MemoryDetailsHeaderProps["memory"],
      deleteMutation: { mutate: jest.fn(), isPending: false },
      handleToggleActive: jest.fn(),
    };
    return { ...base, ...(overrides ?? {}) };
  };

  it("renders memory information", () => {
    const props = makeProps({
      memory: { ...makeProps().memory, is_active: true },
    });
    render(<MemoryDetailsHeader {...props} />);
    expect(screen.getByText("Memory One")).toBeInTheDocument();
    expect(screen.getByText("Enabled")).toBeInTheDocument();
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
    fireEvent.click(screen.getByLabelText(/auto-capture/i));
    expect(props.handleToggleActive).toHaveBeenCalledWith(false);
  });
});
