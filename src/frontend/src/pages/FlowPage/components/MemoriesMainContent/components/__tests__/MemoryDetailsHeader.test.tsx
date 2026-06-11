import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { MemoryInfo } from "@/controllers/API/queries/memories/types";
import { ALL_SESSIONS_VALUE } from "../../hooks/useMemorySessionResolver";
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
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-icon={name} className={className}>
      {name}
    </span>
  ),
}));

jest.mock("@/components/ui/switch", () => ({
  Switch: ({
    checked,
    onCheckedChange,
    "aria-label": ariaLabel,
  }: {
    checked: boolean;
    onCheckedChange: (v: boolean) => void;
    "aria-label"?: string;
  }) => (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      onClick={() => onCheckedChange(!checked)}
    />
  ),
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

jest.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div role="tooltip">{children}</div>
  ),
  TooltipProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
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
    expect(screen.getByText("Activate")).toBeInTheDocument();
    const toggle = screen.getByRole("switch", { name: "Toggle auto-capture" });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-checked", "true");
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
      memory: { ...makeProps().memory, is_active: true },
    });
    render(<MemoryDetailsHeader {...props} />);
    fireEvent.click(
      screen.getByRole("switch", { name: "Toggle auto-capture" }),
    );

    expect(props.handleToggleActive).toHaveBeenCalledWith(false);
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

  it("always enables the session selector regardless of session count", () => {
    const props = makeProps({
      sessions: ["session-1"],
      hasNextSessionsPage: false,
    });
    render(<MemoryDetailsHeader {...props} />);
    expect(
      screen.getByRole("button", { name: "Session filter" }),
    ).not.toBeDisabled();
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
        () =>
          new Promise<void>((res) => {
            resolve = res;
          }),
      );
      const props = makeProps({ onRefresh });
      render(<MemoryDetailsHeader {...props} />);

      const btn = screen.getByRole("button", {
        name: "Reload sessions and messages",
      });
      fireEvent.click(btn);
      expect(btn).toBeDisabled();

      await act(async () => {
        resolve();
      });
    });

    it("shows success toast after onRefresh resolves", async () => {
      const onRefresh = jest.fn().mockResolvedValue(undefined);
      const props = makeProps({ onRefresh });
      render(<MemoryDetailsHeader {...props} />);

      fireEvent.click(
        screen.getByRole("button", { name: "Reload sessions and messages" }),
      );

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

      fireEvent.click(
        screen.getByRole("button", { name: "Reload sessions and messages" }),
      );

      await waitFor(() => {
        expect(mockSetErrorData).toHaveBeenCalled();
      });
      expect(mockSetSuccessData).not.toHaveBeenCalled();
    });

    it("shows error toast with api message when onRefresh rejects", async () => {
      const onRefresh = jest.fn().mockRejectedValue(new Error("timeout"));
      const props = makeProps({ onRefresh });
      render(<MemoryDetailsHeader {...props} />);

      fireEvent.click(
        screen.getByRole("button", { name: "Reload sessions and messages" }),
      );

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

      const btn = screen.getByRole("button", {
        name: "Reload sessions and messages",
      });
      fireEvent.click(btn);

      await waitFor(() => expect(btn).not.toBeDisabled());
    });
  });

  it("shows activate tooltip description", () => {
    render(<MemoryDetailsHeader {...makeProps()} />);
    expect(
      screen.getByText(/conversation messages are automatically processed/i),
    ).toBeInTheDocument();
  });

  it("shows read the docs link in activate tooltip with correct href", () => {
    render(<MemoryDetailsHeader {...makeProps()} />);
    const link = screen.getByRole("link", { name: /read the docs/i });
    expect(link).toHaveAttribute(
      "href",
      "https://docs.langflow.org/memory-bases",
    );
    expect(link).toHaveAttribute("target", "_blank");
  });

  describe("All Sessions dropdown option", () => {
    it("renders 'All Sessions' as the first dropdown item", () => {
      const props = makeProps({ sessions: ["session-1", "session-2"] });
      render(<MemoryDetailsHeader {...props} />);

      const items = screen.getAllByRole("menuitem");
      expect(items[0]).toHaveTextContent("All Sessions");
    });

    it("clicking 'All Sessions' calls setSelectedSession with ALL_SESSIONS_VALUE", () => {
      const setSelectedSession = jest.fn();
      const props = makeProps({
        sessions: ["session-1"],
        setSelectedSession,
      });
      render(<MemoryDetailsHeader {...props} />);

      const allSessionsItem = screen.getAllByRole("menuitem")[0];
      fireEvent.click(allSessionsItem);

      expect(setSelectedSession).toHaveBeenCalledWith(ALL_SESSIONS_VALUE);
    });

    it("shows 'All Sessions' label on trigger when selectedSession is null", () => {
      const props = makeProps({ selectedSession: null });
      render(<MemoryDetailsHeader {...props} />);

      expect(
        screen.getByRole("button", { name: "Session filter" }),
      ).toHaveTextContent("All Sessions");
    });

    it("shows 'All Sessions' label on trigger when selectedSession is ALL_SESSIONS_VALUE", () => {
      const props = makeProps({ selectedSession: ALL_SESSIONS_VALUE });
      render(<MemoryDetailsHeader {...props} />);

      expect(
        screen.getByRole("button", { name: "Session filter" }),
      ).toHaveTextContent("All Sessions");
    });

    it("shows the selected session ID on the trigger when a specific session is active", () => {
      const props = makeProps({ selectedSession: "session-1" });
      render(<MemoryDetailsHeader {...props} />);

      expect(
        screen.getByRole("button", { name: "Session filter" }),
      ).toHaveTextContent("session-1");
    });

    it("marks the 'All Sessions' item as checked when selectedSession is null", () => {
      const props = makeProps({ selectedSession: null });
      render(<MemoryDetailsHeader {...props} />);

      const allSessionsItem = screen.getAllByRole("menuitem")[0];
      const checkIcon = allSessionsItem.querySelector("[data-icon='Check']");
      expect(checkIcon).not.toHaveClass("opacity-0");
    });

    it("marks the 'All Sessions' item as checked when selectedSession is ALL_SESSIONS_VALUE", () => {
      const props = makeProps({ selectedSession: ALL_SESSIONS_VALUE });
      render(<MemoryDetailsHeader {...props} />);

      const allSessionsItem = screen.getAllByRole("menuitem")[0];
      const checkIcon = allSessionsItem.querySelector("[data-icon='Check']");
      expect(checkIcon).not.toHaveClass("opacity-0");
    });

    it("does not mark 'All Sessions' as checked when a specific session is selected", () => {
      const props = makeProps({ selectedSession: "session-1" });
      render(<MemoryDetailsHeader {...props} />);

      const allSessionsItem = screen.getAllByRole("menuitem")[0];
      const checkIcon = allSessionsItem.querySelector("[data-icon='Check']");
      expect(checkIcon).toHaveClass("opacity-0");
    });

    it("marks the matching session item as checked and others as unchecked", () => {
      const props = makeProps({
        sessions: ["session-1", "session-2"],
        selectedSession: "session-2",
      });
      render(<MemoryDetailsHeader {...props} />);

      const items = screen.getAllByRole("menuitem");
      // items[0] = All Sessions, items[1] = session-1, items[2] = session-2
      expect(items[2].querySelector("[data-icon='Check']")).not.toHaveClass(
        "opacity-0",
      );
      expect(items[1].querySelector("[data-icon='Check']")).toHaveClass(
        "opacity-0",
      );
    });

    it("clicking a specific session item calls setSelectedSession with that session id", () => {
      const setSelectedSession = jest.fn();
      const props = makeProps({
        sessions: ["session-1", "session-2"],
        selectedSession: ALL_SESSIONS_VALUE,
        setSelectedSession,
      });
      render(<MemoryDetailsHeader {...props} />);

      const items = screen.getAllByRole("menuitem");
      fireEvent.click(items[1]); // session-1

      expect(setSelectedSession).toHaveBeenCalledWith("session-1");
    });

    it("truncates long session IDs in the trigger button", () => {
      const longId = "a-very-long-session-id-exceeding-limit";
      const props = makeProps({
        sessions: [longId],
        selectedSession: longId,
      });
      render(<MemoryDetailsHeader {...props} />);

      const btn = screen.getByRole("button", { name: "Session filter" });
      expect(btn).toHaveTextContent(`${longId.slice(0, 20)}...`);
    });
  });
});
