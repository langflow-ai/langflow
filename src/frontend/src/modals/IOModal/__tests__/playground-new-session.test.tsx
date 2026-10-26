import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { Message } from "@/types/messages";
import IOModal from "../playground-modal";

jest.mock("@/assets/LangflowLogoColor.svg?react", () => ({
  __esModule: true,
  default: () => <svg />,
}));
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
jest.mock(
  "@/components/core/appHeaderComponent/components/ThemeButtons",
  () => ({
    __esModule: true,
    default: () => null,
  }),
);
jest.mock("../components/selected-view-field", () => ({
  SelectedViewField: () => null,
}));
jest.mock("../components/IOFieldView/components/session-selector", () => ({
  __esModule: true,
  default: ({
    session,
    toggleVisibility,
    deleteSession,
    canRename,
    onSessionRenamed,
  }: {
    session: string;
    toggleVisibility: () => void;
    deleteSession: (session: string) => void;
    canRename?: boolean;
    onSessionRenamed?: (previous: string, next: string) => void;
  }) => (
    <>
      <button
        type="button"
        data-can-rename={canRename}
        onClick={toggleVisibility}
      >
        {session}
      </button>
      <button type="button" onClick={() => deleteSession(session)}>
        Delete {session}
      </button>
      <button
        type="button"
        onClick={() => onSessionRenamed?.(session, `${session}-renamed`)}
      >
        Rename {session}
      </button>
    </>
  ),
}));
jest.mock(
  "@/components/core/playgroundComponent/chat-view/chat-header/components/show-more-sessions",
  () => ({
    ShowMoreSessions: () => null,
  }),
);
jest.mock("../components/chatView/components/chat-view", () => ({
  __esModule: true,
  default: ({
    visibleSession,
    sendMessage,
  }: {
    visibleSession?: string;
    sendMessage: (options: { repeat: number }) => Promise<void>;
  }) => (
    <>
      <p data-testid="visible-session">{visibleSession ?? "none"}</p>
      <button type="button" onClick={() => void sendMessage({ repeat: 1 })}>
        Send
      </button>
    </>
  ),
}));
jest.mock("../../baseModal", () => {
  function Modal({ children }: { children: React.ReactNode }) {
    return <>{children}</>;
  }
  Modal.Trigger = Modal;
  Modal.Content = Modal;
  return { __esModule: true, default: Modal };
});
let mockFlowId = "test-flow-id";
jest.mock("../hooks/useGetFlowId", () => ({
  useGetFlowId: () => mockFlowId,
}));
jest.mock(
  "../components/chatView/chatInput/components/voice-assistant/helpers/create-new-session-name",
  () => ({
    createNewSessionName: () => "Session fixed-time",
  }),
);
let mockAuthenticatedPlayground = true;
jest.mock("@/modals/IOModal/helpers/playground-auth", () => ({
  isAuthenticatedPlayground: () => mockAuthenticatedPlayground,
}));
jest.mock("@/customization/utils/analytics", () => ({ track: jest.fn() }));
jest.mock("@/customization/utils/custom-open-new-tab", () => ({
  customOpenNewTab: jest.fn(),
}));
jest.mock("@/customization/utils/urls", () => ({
  LangflowButtonRedirectTarget: () => "https://langflow.org",
}));
jest.mock("@/customization/feature-flags", () => ({ ENABLE_PUBLISH: false }));

const messagesQuery = { isFetched: true, refetch: jest.fn() };
const sessionsQuery = {
  data: ["test-flow-id", "test-flow-id:existing"],
  isLoading: false,
  refetch: jest.fn(),
};
const deleteSessionQuery = { mutate: jest.fn() };
jest.mock("@/controllers/API/queries/messages/use-get-message-history", () => ({
  useGetMessageHistory: () => messagesQuery,
}));
jest.mock(
  "@/controllers/API/queries/messages/use-get-sessions-from-flow",
  () => ({
    useGetSessionsFromFlowQuery: () => sessionsQuery,
  }),
);
jest.mock("@/controllers/API/queries/messages/use-delete-sessions", () => ({
  useDeleteSession: () => deleteSessionQuery,
}));

const flowState = {
  inputs: [{ id: "chat-input", type: "ChatInput" }],
  outputs: [],
  nodes: [],
  buildFlow: jest.fn(),
  setIsBuilding: jest.fn(),
  isBuilding: false,
  newChatOnPlayground: false,
  setNewChatOnPlayground: jest.fn((value: boolean) => {
    flowState.newChatOnPlayground = value;
  }),
  currentFlow: { id: "test-flow-id", name: "Test flow" },
};
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: typeof flowState) => unknown) =>
    selector(flowState),
}));
const managerState = { setIOModalOpen: jest.fn() };
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: typeof managerState) => unknown) =>
    selector(managerState),
}));
const alertState = { setErrorData: jest.fn(), setSuccessData: jest.fn() };
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: typeof alertState) => unknown) =>
    selector(alertState),
}));
const voiceState = { setNewSessionCloseVoiceAssistant: jest.fn() };
jest.mock("@/stores/voiceStore", () => ({
  useVoiceStore: (selector: (state: typeof voiceState) => unknown) =>
    selector(voiceState),
}));
const messagesState = {
  deleteSession: jest.fn(),
  removeMessages: jest.fn(),
  messages: [] as Message[],
};
jest.mock("@/stores/messagesStore", () => ({
  useMessagesStore: (selector: (state: typeof messagesState) => unknown) =>
    selector(messagesState),
}));
const utilityState = {
  setCurrentSessionId: jest.fn(),
  chatValueStore: "First question",
  setChatValueStore: jest.fn(),
  eventDelivery: "polling",
  setPlaygroundScrollBehaves: jest.fn(),
};
jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: (selector: (state: typeof utilityState) => unknown) =>
    selector(utilityState),
}));

const playground = () => (
  <IOModal open setOpen={jest.fn()} isPlayground playgroundPage>
    <div />
  </IOModal>
);
const activeSession = () => screen.getByTestId("visible-session").textContent!;

beforeEach(() => {
  jest.clearAllMocks();
  mockFlowId = "test-flow-id";
  flowState.newChatOnPlayground = false;
  mockAuthenticatedPlayground = true;
  flowState.buildFlow.mockResolvedValue(undefined);
  sessionsQuery.data = ["test-flow-id", "test-flow-id:existing"];
  sessionsQuery.refetch.mockResolvedValue({ data: sessionsQuery.data });
  messagesState.messages = [];
});

it.each(["sidebar", "header"])(
  "selects the session created from the %s before sending",
  async (entry) => {
    render(playground());
    if (entry === "header") {
      fireEvent.click(screen.getByRole("button", { name: "Hide sidebar" }));
      fireEvent.click(screen.getByRole("button", { name: "New Chat" }));
    } else {
      fireEvent.click(screen.getByTestId("new-chat"));
    }

    const selected = activeSession();
    expect(selected).toBe("test-flow-id:Session fixed-time");
    expect(utilityState.setCurrentSessionId).toHaveBeenLastCalledWith(selected);
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(flowState.buildFlow).toHaveBeenCalledWith(
        expect.objectContaining({
          input_value: "First question",
          session: selected,
        }),
      ),
    );
  },
);

it("keeps the new session selected while older server results arrive", async () => {
  const view = render(playground());
  fireEvent.click(screen.getByTestId("new-chat"));
  const selected = activeSession();
  expect(selected).not.toBe("none");

  messagesState.messages = [
    { session_id: selected, text: "First question" } as Message,
  ];
  sessionsQuery.data = ["test-flow-id:older"];
  view.rerender(playground());
  await act(async () => {});

  expect(activeSession()).toBe(selected);
  expect(screen.getByRole("button", { name: selected })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "test-flow-id:older" }));
  expect(activeSession()).toBe("test-flow-id:older");
  fireEvent.click(screen.getByRole("button", { name: "test-flow-id" }));
  expect(activeSession()).toBe("test-flow-id");
});

it("creates distinct sessions for consecutive clicks with the same timestamp", () => {
  render(playground());
  fireEvent.click(screen.getByTestId("new-chat"));
  const first = activeSession();
  fireEvent.click(screen.getByTestId("new-chat"));
  const second = activeSession();
  expect(first).not.toBe("none");
  expect(second).not.toBe(first);
  expect(screen.getByRole("button", { name: first })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: second })).toBeInTheDocument();
});

it("keeps a later selection when the send's session refresh completes", async () => {
  let finishRefresh!: (value: { data: string[] }) => void;
  sessionsQuery.refetch.mockReturnValue(
    new Promise((resolve) => {
      finishRefresh = resolve;
    }),
  );
  render(playground());
  fireEvent.click(screen.getByTestId("new-chat"));
  const created = activeSession();
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(sessionsQuery.refetch).toHaveBeenCalled());
  fireEvent.click(
    screen.getByRole("button", { name: "test-flow-id:existing" }),
  );
  await act(async () => {
    finishRefresh({ data: [created] });
  });
  expect(activeSession()).toBe("test-flow-id:existing");
});

it("enables renaming when the new session is returned by the server", () => {
  const view = render(playground());
  fireEvent.click(screen.getByTestId("new-chat"));
  const created = activeSession();
  expect(screen.getByRole("button", { name: created })).toHaveAttribute(
    "data-can-rename",
    "false",
  );
  sessionsQuery.data = [created];
  view.rerender(playground());
  expect(screen.getByRole("button", { name: created })).toHaveAttribute(
    "data-can-rename",
    "true",
  );
});

it("removes a deleted local session from subsequent server refreshes", () => {
  const view = render(playground());
  fireEvent.click(screen.getByTestId("new-chat"));
  const created = activeSession();
  fireEvent.click(screen.getByRole("button", { name: `Delete ${created}` }));
  act(() => {
    deleteSessionQuery.mutate.mock.calls[0][1].onSuccess();
  });
  sessionsQuery.data = [created];
  view.rerender(playground());
  expect(
    screen.queryByRole("button", { name: created }),
  ).not.toBeInTheDocument();
  expect(activeSession()).toBe("test-flow-id");
});

it("retains a confirmed local session through a stale server result", () => {
  const view = render(playground());
  fireEvent.click(screen.getByTestId("new-chat"));
  const created = activeSession();
  sessionsQuery.data = [created];
  view.rerender(playground());

  sessionsQuery.data = [];
  view.rerender(playground());

  expect(screen.getByRole("button", { name: created })).toHaveAttribute(
    "data-can-rename",
    "true",
  );
  expect(activeSession()).toBe(created);
});

it("starts with the new flow's session after a route change", async () => {
  const view = render(playground());
  fireEvent.click(screen.getByTestId("new-chat"));
  const previous = activeSession();
  mockFlowId = "next-flow-id";
  sessionsQuery.data = [mockFlowId];
  view.rerender(playground());

  expect(activeSession()).toBe(mockFlowId);
  expect(
    screen.queryByRole("button", { name: previous }),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() =>
    expect(flowState.buildFlow).toHaveBeenLastCalledWith(
      expect.objectContaining({ session: mockFlowId }),
    ),
  );
});

it("can reuse the name of a deleted local session", () => {
  const view = render(playground());
  fireEvent.click(screen.getByTestId("new-chat"));
  const created = activeSession();
  fireEvent.click(screen.getByRole("button", { name: `Delete ${created}` }));
  act(() => deleteSessionQuery.mutate.mock.calls[0][1].onSuccess());
  fireEvent.click(screen.getByTestId("new-chat"));
  sessionsQuery.data = [created];
  view.rerender(playground());

  expect(activeSession()).toBe(created);
  expect(screen.getByRole("button", { name: created })).toBeInTheDocument();
});

it("retains a renamed local session and filters its previous name", () => {
  const view = render(playground());
  fireEvent.click(screen.getByTestId("new-chat"));
  const created = activeSession();
  sessionsQuery.data = [created];
  view.rerender(playground());
  fireEvent.click(screen.getByRole("button", { name: `Rename ${created}` }));
  sessionsQuery.data = [created];
  view.rerender(playground());

  expect(
    screen.queryByRole("button", { name: created }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: `${created}-renamed` }),
  ).toHaveAttribute("data-can-rename", "true");
});

it("persists anonymous messages with the selected session", () => {
  mockAuthenticatedPlayground = false;
  const view = render(playground());
  fireEvent.click(screen.getByTestId("new-chat"));
  const created = activeSession();
  messagesState.messages = [
    {
      flow_id: "test-flow-id",
      session_id: created,
      text: "First question",
    } as Message,
  ];
  view.rerender(playground());
  expect(JSON.parse(window.sessionStorage.getItem("test-flow-id")!)).toEqual(
    messagesState.messages,
  );
  expect(activeSession()).toBe(created);
});

it("preserves the next flow's stored history while old messages remain in the store", () => {
  mockAuthenticatedPlayground = false;
  const previous = {
    flow_id: "test-flow-id",
    session_id: "test-flow-id",
    text: "Previous",
  } as Message;
  const next = {
    flow_id: "next-flow-id",
    session_id: "next-flow-id",
    text: "Next",
  } as Message;
  messagesState.messages = [previous];
  window.sessionStorage.setItem("next-flow-id", JSON.stringify([next]));
  const view = render(playground());

  mockFlowId = "next-flow-id";
  sessionsQuery.data = [mockFlowId];
  view.rerender(playground());
  expect(JSON.parse(window.sessionStorage.getItem(mockFlowId)!)).toEqual([
    next,
  ]);

  messagesState.messages = [previous, next];
  view.rerender(playground());
  expect(JSON.parse(window.sessionStorage.getItem(mockFlowId)!)).toEqual([
    next,
  ]);
});
