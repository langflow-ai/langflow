import { fireEvent, render, screen } from "@testing-library/react";
import type { MemoryInfo } from "@/controllers/API/queries/memories/types";
import type { MemoryDetailsHeaderProps } from "../../types";
import { MemoryDetailsHeader } from "../MemoryDetailsHeader";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span>{name}</span>,
}));

jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  DropdownMenuContent: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <div className={className}>{children}</div>,
  DropdownMenuItem: ({
    children,
    onSelect,
    className,
  }: {
    children: React.ReactNode;
    onSelect?: (e: Event) => void;
    className?: string;
  }) => (
    <div
      role="menuitem"
      className={className}
      onClick={(e) => onSelect?.(e as unknown as Event)}
    >
      {children}
    </div>
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
      onRefresh: jest.fn(),
      fetchNextSessionsPage: jest.fn(),
      hasNextSessionsPage: false,
      isFetchingNextSessionsPage: false,
    };
    return { ...base, ...(overrides ?? {}) };
  };

  it("renders memory information with the ON state badge when active", () => {
    const props = makeProps({
      memory: { ...makeProps().memory, is_active: true },
    });
    render(<MemoryDetailsHeader {...props} />);
    expect(screen.getByText("Memory One")).toBeInTheDocument();
    const toggleButton = screen.getByRole("button", {
      name: "Disable auto-capture",
    });
    expect(toggleButton).toHaveTextContent("Auto-capture");
    expect(toggleButton).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByTestId("memory-auto-capture-toggle-state"),
    ).toHaveTextContent("ON");
  });

  it("renders the OFF state badge and enable aria-label when inactive", () => {
    const props = makeProps({
      memory: { ...makeProps().memory, is_active: false },
    });
    render(<MemoryDetailsHeader {...props} />);
    const toggleButton = screen.getByRole("button", {
      name: "Enable auto-capture",
    });
    expect(toggleButton).toHaveAttribute("aria-pressed", "false");
    expect(
      screen.getByTestId("memory-auto-capture-toggle-state"),
    ).toHaveTextContent("OFF");
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
    const props = makeProps({
      memory: { ...makeProps().memory, is_active: false },
    });
    render(<MemoryDetailsHeader {...props} />);
    fireEvent.click(
      screen.getByRole("button", { name: "Enable auto-capture" }),
    );

    const firstCallArg = (props.handleToggleActive as jest.Mock).mock
      .calls[0]?.[0];
    expect(firstCallArg).toEqual(expect.any(Function));
    expect(firstCallArg(true)).toBe(false);
  });

  it("renders the session selector when sessions exist", () => {
    const props = makeProps({ sessions: ["session-1", "session-2"] });
    render(<MemoryDetailsHeader {...props} />);

    const sessionTrigger = screen.getByRole("button", {
      name: "Session filter",
    });
    expect(sessionTrigger).toBeInTheDocument();
    expect(sessionTrigger).not.toBeDisabled();
  });

  it("disables the session selector when only one session and no more pages", () => {
    const props = makeProps({
      sessions: ["session-1"],
      hasNextSessionsPage: false,
    });
    render(<MemoryDetailsHeader {...props} />);
    expect(
      screen.getByRole("button", { name: "Session filter" }),
    ).toBeDisabled();
  });

  it("renders the reload button with correct aria-label", () => {
    const props = makeProps();
    render(<MemoryDetailsHeader {...props} />);
    expect(
      screen.getByRole("button", { name: "Reload sessions and messages" }),
    ).toBeInTheDocument();
  });

  it("calls onRefresh when the reload button is clicked", () => {
    const onRefresh = jest.fn();
    const props = makeProps({ onRefresh });
    render(<MemoryDetailsHeader {...props} />);
    fireEvent.click(
      screen.getByRole("button", { name: "Reload sessions and messages" }),
    );
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("renders the RefreshCw icon inside the reload button", () => {
    const props = makeProps();
    render(<MemoryDetailsHeader {...props} />);
    const reloadBtn = screen.getByRole("button", {
      name: "Reload sessions and messages",
    });
    expect(reloadBtn).toHaveTextContent("RefreshCw");
  });

  it("calls fetchNextSessionsPage on scroll when near bottom and more pages exist", () => {
    const fetchNextSessionsPage = jest.fn();
    const props = makeProps({
      sessions: ["s1", "s2", "s3"],
      hasNextSessionsPage: true,
      isFetchingNextSessionsPage: false,
      fetchNextSessionsPage,
    });
    const { container } = render(<MemoryDetailsHeader {...props} />);

    const scrollDiv = container.querySelector(".overflow-y-auto");
    if (!scrollDiv) return;

    Object.defineProperty(scrollDiv, "scrollHeight", {
      value: 400,
      configurable: true,
    });
    Object.defineProperty(scrollDiv, "scrollTop", {
      value: 200,
      configurable: true,
    });
    Object.defineProperty(scrollDiv, "clientHeight", {
      value: 240,
      configurable: true,
    });

    fireEvent.scroll(scrollDiv);
    expect(fetchNextSessionsPage).toHaveBeenCalledTimes(1);
  });

  it("does not call fetchNextSessionsPage when already fetching next page", () => {
    const fetchNextSessionsPage = jest.fn();
    const props = makeProps({
      sessions: ["s1", "s2", "s3"],
      hasNextSessionsPage: true,
      isFetchingNextSessionsPage: true,
      fetchNextSessionsPage,
    });
    const { container } = render(<MemoryDetailsHeader {...props} />);

    const scrollDiv = container.querySelector(".overflow-y-auto");
    if (!scrollDiv) return;

    Object.defineProperty(scrollDiv, "scrollHeight", {
      value: 400,
      configurable: true,
    });
    Object.defineProperty(scrollDiv, "scrollTop", {
      value: 200,
      configurable: true,
    });
    Object.defineProperty(scrollDiv, "clientHeight", {
      value: 240,
      configurable: true,
    });

    fireEvent.scroll(scrollDiv);
    expect(fetchNextSessionsPage).not.toHaveBeenCalled();
  });

  it("does not call fetchNextSessionsPage when no more pages exist", () => {
    const fetchNextSessionsPage = jest.fn();
    const props = makeProps({
      sessions: ["s1", "s2"],
      hasNextSessionsPage: false,
      isFetchingNextSessionsPage: false,
      fetchNextSessionsPage,
    });
    const { container } = render(<MemoryDetailsHeader {...props} />);

    const scrollDiv = container.querySelector(".overflow-y-auto");
    if (!scrollDiv) return;

    Object.defineProperty(scrollDiv, "scrollHeight", {
      value: 400,
      configurable: true,
    });
    Object.defineProperty(scrollDiv, "scrollTop", {
      value: 300,
      configurable: true,
    });
    Object.defineProperty(scrollDiv, "clientHeight", {
      value: 240,
      configurable: true,
    });

    fireEvent.scroll(scrollDiv);
    expect(fetchNextSessionsPage).not.toHaveBeenCalled();
  });

  it("shows a loading indicator while fetching next page", () => {
    const props = makeProps({
      sessions: ["s1", "s2"],
      hasNextSessionsPage: true,
      isFetchingNextSessionsPage: true,
    });
    const { container } = render(<MemoryDetailsHeader {...props} />);

    const scrollDiv = container.querySelector(".overflow-y-auto");
    expect(scrollDiv).not.toBeNull();
    expect(scrollDiv).toHaveTextContent("Loading");
  });
});
