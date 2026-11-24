import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { useGetMessageHistory } from "@/controllers/API/queries/messages/use-get-message-history";
import { useMessagesStore } from "@/stores/messagesStore";
import type { Message } from "@/types/messages";
import { ChatViewWrapper } from "../chat-view-wrapper";
import SessionView from "../session-view";

const mockGet = jest.fn();
let mockPlayground = false;
jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => mockGet(...args) },
}));
jest.mock("@/stores/flowStore", () => {
  const state = () => ({ playgroundPage: mockPlayground });
  return {
    __esModule: true,
    default: Object.assign((selector) => selector(state()), {
      getState: state,
    }),
  };
});
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: { getState: () => ({ currentFlowId: "source-flow" }) },
}));
jest.mock("@/modals/IOModal/helpers/playground-auth", () => ({
  isAuthenticatedPlayground: () => mockPlayground,
}));
jest.mock("@/controllers/API/queries/messages", () => ({
  useDeleteMessages: () => ({ mutate: jest.fn() }),
  useUpdateMessage: () => ({ mutate: jest.fn() }),
}));
jest.mock(
  "@/components/core/playgroundComponent/chat-view/utils/message-utils",
  () => ({ removeMessages: jest.fn() }),
);
jest.mock("@/utils/utils", () => ({
  prepareSessionIdForAPI: (id: string) => encodeURIComponent(id),
  extractColumnsFromRows: () => [],
  messagesSorter: () => 0,
  cn: (...args: unknown[]) => args.filter(Boolean).join(" "),
}));
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: PropsWithChildren) => children,
}));
jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => ({
    __esModule: true,
    default: ({ rowData }: { rowData: Message[] }) => (
      <div data-testid="message-table">
        {rowData.map((m) => (
          <p key={m.id}>{m.text}</p>
        ))}
      </div>
    ),
  }),
);
jest.mock("../chatView/components/chat-view", () => ({
  __esModule: true,
  default: () => {
    const messages = useMessagesStore((state) => state.messages);
    return (
      <div data-testid="message-chat">
        {messages.map((m) => (
          <p key={m.id}>{m.text}</p>
        ))}
      </div>
    );
  },
}));

function SharedChat() {
  const messageHistory = useGetMessageHistory({
    id: "flow",
    sessionId: "session",
  });
  return (
    <ChatViewWrapper
      messageHistory={messageHistory}
      messagesFetched={messageHistory.isFetched}
      selectedViewField={undefined}
      visibleSession="session"
      sessions={["session"]}
      sidebarOpen={false}
      currentFlowId="flow"
      setSidebarOpen={() => {}}
      isPlayground
      setvisibleSession={() => {}}
      setSelectedViewField={() => {}}
      haveChat={undefined}
      sessionId="session"
      sendMessage={async () => {}}
      canvasOpen={false}
      setOpen={() => {}}
      playgroundTitle="Test"
      playgroundPage
    />
  );
}

beforeEach(() => {
  mockGet.mockReset();
  mockPlayground = false;
  useMessagesStore.getState().clearMessages();
  mockGet.mockImplementation(async (_url, { params }) => ({
    data: Array.from({ length: 205 }, (_, i) => ({
      id: `message-${204 - i}`,
      text: `Message ${204 - i}`,
      flow_id: "flow",
      session_id: "session",
      timestamp: new Date(Date.UTC(2026, 0, 1, 0, 204 - i)).toISOString(),
    })).slice(params.offset, params.offset + params.limit),
  }));
});

it.each(["table", "chat"])(
  "lets the %s load messages beyond the initial cap",
  async (view) => {
    mockPlayground = view === "chat";
    const client = new QueryClient({
      defaultOptions: { queries: { gcTime: 0 } },
    });
    render(
      <QueryClientProvider client={client}>
        {view === "chat" ? <SharedChat /> : <SessionView />}
      </QueryClientProvider>,
    );
    await screen.findByText("Message 204");
    expect(screen.queryByText("Message 104")).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: /load older messages/i }),
    );
    await screen.findByText("Message 104");
    expect(screen.getByText("Message 204")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: /load older messages/i }),
    );
    await screen.findByText("Message 0");
    await waitFor(() =>
      expect(
        screen.queryByTestId("load-older-messages"),
      ).not.toBeInTheDocument(),
    );
    expect(
      mockGet.mock.calls.map(([, config]) => config.params.offset),
    ).toEqual([0, 100, 200]);
  },
);

it("keeps loaded messages visible when an older-page request fails and can retry", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { gcTime: 0 } },
  });
  render(
    <QueryClientProvider client={client}>
      <SessionView />
    </QueryClientProvider>,
  );
  await screen.findByText("Message 204");
  mockGet.mockRejectedValueOnce({
    isAxiosError: true,
    response: { status: 400 },
  });
  fireEvent.click(screen.getByRole("button", { name: /load older messages/i }));
  await screen.findByRole("alert");
  expect(screen.getByText("Message 204")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /retry/i }));
  await screen.findByText("Message 104");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(mockGet.mock.calls.map(([, config]) => config.params.offset)).toEqual([
    0, 100, 100,
  ]);
});
