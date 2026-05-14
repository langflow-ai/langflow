import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { MemoryInfo } from "@/controllers/API/queries/memories/types";
import type { MemoryDetailsHeaderProps } from "../../types";
import { MemoryDetailsHeader } from "../MemoryDetailsHeader";

const mockSetSuccessData = jest.fn();
const mockSetErrorData = jest.fn();

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: unknown) => unknown) =>
    selector({
      setSuccessData: mockSetSuccessData,
      setErrorData: mockSetErrorData,
    }),
}));

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

beforeEach(() => {
  jest.clearAllMocks();
});

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

  it("renders memory information", () => {
    const props = makeProps({
      memory: { ...makeProps().memory, is_active: true },
    });
    render(<MemoryDetailsHeader {...props} />);
    expect(screen.getByText("Memory One")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Toggle auto-capture" }),
    ).toHaveTextContent("Auto-capture");
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

  describe("handleRefresh", () => {
    it("disables the refresh button while refreshing", async () => {
      let resolve!: () => void;
      const onRefresh = jest.fn(
        () => new Promise<void>((res) => { resolve = res; }),
      );
      const props = makeProps({ onRefresh });
      render(<MemoryDetailsHeader {...props} />);

      const btn = screen.getByRole("button", { name: "Reload sessions and messages" });
      fireEvent.click(btn);
      expect(btn).toBeDisabled();

      await act(async () => { resolve(); });
    });

    it("shows success toast after onRefresh resolves", async () => {
      const onRefresh = jest.fn().mockResolvedValue(undefined);
      const props = makeProps({ onRefresh });
      render(<MemoryDetailsHeader {...props} />);

      fireEvent.click(screen.getByRole("button", { name: "Reload sessions and messages" }));

      await waitFor(() => {
        expect(mockSetSuccessData).toHaveBeenCalledWith({
          title: `Memory "Memory One" refreshed`,
        });
      });
    });

    it("does not show success toast when onRefresh rejects", async () => {
      const onRefresh = jest.fn().mockRejectedValue(new Error("network"));
      const props = makeProps({ onRefresh });
      render(<MemoryDetailsHeader {...props} />);

      fireEvent.click(screen.getByRole("button", { name: "Reload sessions and messages" }));

      await waitFor(() => {
        expect(mockSetErrorData).toHaveBeenCalled();
      });
      expect(mockSetSuccessData).not.toHaveBeenCalled();
    });

    it("shows error toast with api message when onRefresh rejects", async () => {
      const onRefresh = jest.fn().mockRejectedValue(new Error("timeout"));
      const props = makeProps({ onRefresh });
      render(<MemoryDetailsHeader {...props} />);

      fireEvent.click(screen.getByRole("button", { name: "Reload sessions and messages" }));

      await waitFor(() => {
        expect(mockSetErrorData).toHaveBeenCalledWith({
          title: "Failed to refresh memory",
          list: ["timeout"],
        });
      });
    });

    it("re-enables the refresh button after onRefresh rejects", async () => {
      const onRefresh = jest.fn().mockRejectedValue(new Error("fail"));
      const props = makeProps({ onRefresh });
      render(<MemoryDetailsHeader {...props} />);

      const btn = screen.getByRole("button", { name: "Reload sessions and messages" });
      fireEvent.click(btn);

      await waitFor(() => expect(btn).not.toBeDisabled());
    });
  });
});
