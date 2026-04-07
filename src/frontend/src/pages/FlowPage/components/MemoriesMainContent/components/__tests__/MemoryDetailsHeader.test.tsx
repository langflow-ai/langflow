import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryDetailsHeader } from "../MemoryDetailsHeader";
import type { MemoryDetailsHeaderProps } from "../../types";
import type { MemoryInfo } from "@/controllers/API/queries/memories/types";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span>{name}</span>,
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
    const memory: MemoryInfo = {
      id: "m1",
      name: "Memory One",
      description: "desc",
      kb_name: "kb-1",
      embedding_model: "text-embedding-3-small",
      embedding_provider: "openai",
      is_active: true,
      total_messages_processed: 0,
      sessions_count: 1,
      batch_size: 1,
      preprocessing_enabled: false,
      pending_messages_count: 0,
      user_id: "u1",
      flow_id: "flow-1",
    };

    const base: MemoryDetailsHeaderProps = {
      memory,
      sessions: ["session-1"],
      selectedSession: null,
      setSelectedSession: jest.fn(),
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
    expect(
      screen.getByRole("button", { name: "Toggle auto-capture" }),
    ).toHaveTextContent("Auto-capture: Enabled");
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
    fireEvent.click(
      screen.getByRole("button", { name: "Toggle auto-capture" }),
    );
    expect(props.handleToggleActive).toHaveBeenCalledWith(false);
  });

  it("renders the session selector when sessions exist", () => {
    const props = makeProps({ sessions: ["session-1", "session-2"] });
    render(<MemoryDetailsHeader {...props} />);

    expect(screen.getByLabelText("Session filter")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "session-1" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "session-2" })).toBeInTheDocument();
    expect(screen.getByLabelText("Session filter")).not.toBeDisabled();
  });

  it("disables the session selector when only one session exists", () => {
    const props = makeProps({ sessions: ["session-1"] });
    render(<MemoryDetailsHeader {...props} />);
    expect(screen.getByLabelText("Session filter")).toBeDisabled();
  });
});
