import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useMessagesStore } from "@/stores/messagesStore";
import type { Message } from "@/types/messages";
import IOModal from "../playground-modal";

// Only the "new chat" selection is under test, so the panels around it are
// stubbed: the chat view exposes which session is visible and which id the
// next message is sent under, and the sidebar exposes the new-chat action.

jest.mock("@/assets/LangflowLogoColor.svg?react", () => ({
  __esModule: true,
  default: () => <svg />,
}));

jest.mock(
  "@/components/core/appHeaderComponent/components/ThemeButtons",
  () => ({
    __esModule: true,
    default: () => null,
  }),
);

jest.mock("../components/chat-view-wrapper", () => ({
  __esModule: true,
  ChatViewWrapper: ({
    visibleSession,
    sessionId,
  }: {
    visibleSession?: string;
    sessionId: string;
  }) => (
    <>
      <output data-testid="visible-session">{visibleSession ?? ""}</output>
      <output data-testid="send-session">{sessionId}</output>
    </>
  ),
}));

jest.mock("../components/selected-view-field", () => ({
  __esModule: true,
  SelectedViewField: () => null,
}));

jest.mock("../components/sidebar-open-view", () => ({
  __esModule: true,
  SidebarOpenView: ({
    setvisibleSession,
  }: {
    setvisibleSession: (session: string | undefined) => void;
  }) => (
    <button type="button" onClick={() => setvisibleSession(undefined)}>
      new chat
    </button>
  ),
}));

jest.mock("../../baseModal", () => {
  function MockBaseModal({ children }: { children: React.ReactNode }) {
    return <div>{children}</div>;
  }
  MockBaseModal.Trigger = ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  );
  MockBaseModal.Content = ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  );
  return { __esModule: true, default: MockBaseModal };
});

jest.mock("../hooks/useGetFlowId", () => ({
  __esModule: true,
  useGetFlowId: () => "test-flow-id",
}));

jest.mock("@/modals/IOModal/helpers/playground-auth", () => ({
  __esModule: true,
  isAuthenticatedPlayground: () => true,
}));

jest.mock("@/customization/utils/analytics", () => ({
  __esModule: true,
  track: jest.fn(),
}));

jest.mock("@/customization/utils/custom-open-new-tab", () => ({
  __esModule: true,
  customOpenNewTab: jest.fn(),
}));

jest.mock("@/customization/utils/urls", () => ({
  __esModule: true,
  LangflowButtonRedirectTarget: () => "https://langflow.org",
}));

const messagesQueryResult = { isFetched: true, refetch: jest.fn() };
jest.mock("@/controllers/API/queries/messages/use-get-message-history", () => ({
  __esModule: true,
  useGetMessageHistory: () => messagesQueryResult,
}));

const deleteSessionResult = { mutate: jest.fn() };
jest.mock("@/controllers/API/queries/messages/use-delete-sessions", () => ({
  __esModule: true,
  useDeleteSession: () => deleteSessionResult,
}));

// Newest first, as the server lists them: picking by position would land on
// an old conversation.
const refetchedSessions = ["test-flow-id", "older-session", "oldest-session"];
const sessionsQueryResult = {
  data: refetchedSessions,
  isLoading: false,
  refetch: jest.fn(async () => ({ data: refetchedSessions })),
};
jest.mock(
  "@/controllers/API/queries/messages/use-get-sessions-from-flow",
  () => ({
    __esModule: true,
    useGetSessionsFromFlowQuery: () => sessionsQueryResult,
  }),
);

const flowState = {
  inputs: [],
  outputs: [],
  nodes: [],
  buildFlow: jest.fn(),
  setIsBuilding: jest.fn(),
  isBuilding: false,
  newChatOnPlayground: false,
  setNewChatOnPlayground: jest.fn(),
  currentFlow: {
    icon: undefined,
    id: "test-flow-id",
    gradient: "1",
    name: "Test Flow",
  },
};
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: typeof flowState) => unknown) =>
    selector(flowState),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: { setIOModalOpen: () => void }) => unknown) =>
    selector({ setIOModalOpen: jest.fn() }),
}));

const utilityState = {
  setCurrentSessionId: jest.fn(),
  chatValueStore: "",
  setChatValueStore: jest.fn(),
  eventDelivery: "polling",
  setPlaygroundScrollBehaves: jest.fn(),
};
jest.mock("@/stores/utilityStore", () => ({
  __esModule: true,
  useUtilityStore: (selector: (state: typeof utilityState) => unknown) =>
    selector(utilityState),
}));

function renderModal(playgroundPage: boolean) {
  return render(
    <TooltipProvider>
      <IOModal
        open
        setOpen={jest.fn()}
        isPlayground
        playgroundPage={playgroundPage}
        canvasOpen={false}
      >
        <div />
      </IOModal>
    </TooltipProvider>,
  );
}

// The backend's `scope_session_to_namespace`: prefix unless already scoped.
const scopeToNamespace = (sessionId: string, namespace: string) =>
  sessionId === namespace || sessionId.startsWith(`${namespace}:`)
    ? sessionId
    : `${namespace}:${sessionId}`;

// A message arrives in the store under `sessionId`, as the server stored it.
function receiveMessage(sessionId: string) {
  flowState.newChatOnPlayground = true;
  act(() => {
    useMessagesStore.getState().setMessages([
      {
        id: `message-${sessionId}`,
        flow_id: "test-flow-id",
        session_id: sessionId,
        text: "hello",
        sender: "User",
        sender_name: "User",
        timestamp: new Date().toISOString(),
        files: [],
        edit: false,
        background_color: "",
        text_color: "",
      } satisfies Message,
    ]);
  });
}

describe("IOModal (playground) new chat", () => {
  afterEach(() => {
    flowState.newChatOnPlayground = false;
    act(() => useMessagesStore.getState().setMessages([]));
    sessionsQueryResult.data = refetchedSessions;
    sessionsQueryResult.refetch.mockClear();
  });

  it("selects the new chat under the id the server stores it as", async () => {
    renderModal(true);

    fireEvent.click(screen.getByRole("button", { name: "new chat" }));
    const sentSessionId = screen.getByTestId("send-session").textContent ?? "";
    const storedSessionId = scopeToNamespace(sentSessionId, "test-flow-id");
    expect(storedSessionId).toMatch(/^test-flow-id:Session /);
    expect(sentSessionId).toBe(storedSessionId);

    // Opening the new chat loads history first; that must not select it yet.
    receiveMessage("test-flow-id");
    expect(sessionsQueryResult.refetch).not.toHaveBeenCalled();
    expect(screen.getByTestId("visible-session")).toBeEmptyDOMElement();

    // Newest first, as the server lists them after the send.
    sessionsQueryResult.data = [
      "test-flow-id",
      storedSessionId,
      ...refetchedSessions.slice(1),
    ];
    receiveMessage(storedSessionId);

    await waitFor(() =>
      expect(screen.getByTestId("visible-session")).toHaveTextContent(
        storedSessionId,
      ),
    );
    expect(sessionsQueryResult.refetch).toHaveBeenCalled();
  });

  it("keeps the new session unprefixed outside the playground page", () => {
    renderModal(false);
    fireEvent.click(screen.getByRole("button", { name: "new chat" }));
    expect(screen.getByTestId("send-session")).toHaveTextContent(/^Session /);
  });
});
