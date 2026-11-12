import { fireEvent, render, screen } from "@testing-library/react";
import AgentTestConversation from "../AgentTestConversation";

const mockSendMessage = jest.fn();

jest.mock("@/controllers/API/queries/a2a/use-post-a2a-message", () => ({
  usePostA2AMessage: () => ({
    mutateAsync: mockSendMessage,
    isPending: false,
  }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

describe("AgentTestConversation", () => {
  const originalScrollTo = HTMLElement.prototype.scrollTo;

  beforeAll(() => {
    HTMLElement.prototype.scrollTo = jest.fn();
  });

  afterAll(() => {
    HTMLElement.prototype.scrollTo = originalScrollTo;
  });

  beforeEach(() => {
    jest.clearAllMocks();
    mockSendMessage.mockResolvedValue({
      result: { status: { state: "completed" } },
    });
  });

  it("waits for the agent card before sending with Enter or the button", () => {
    const { rerender } = render(
      <AgentTestConversation
        flowId="flow-1"
        isPublished
        serverEnabled
        cardReady={false}
        requiresApiKey={false}
      />,
    );
    const input = screen.getByTestId("agent-test-input");
    fireEvent.change(input, { target: { value: "hello" } });
    expect(screen.getByTestId("agent-test-send")).toBeDisabled();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(mockSendMessage).not.toHaveBeenCalled();

    // The loaded card reveals that this agent requires authentication.
    rerender(
      <AgentTestConversation
        flowId="flow-1"
        isPublished
        serverEnabled
        cardReady
        requiresApiKey
      />,
    );
    expect(screen.getByTestId("agent-test-send")).toBeDisabled();
    fireEvent.change(screen.getByTestId("agent-test-apikey"), {
      target: { value: "test-key" },
    });
    expect(screen.getByTestId("agent-test-send")).toBeEnabled();
  });

  it("allows a public agent once its card has loaded", () => {
    render(
      <AgentTestConversation
        flowId="flow-1"
        isPublished
        serverEnabled
        cardReady
        requiresApiKey={false}
      />,
    );
    fireEvent.change(screen.getByTestId("agent-test-input"), {
      target: { value: "hello" },
    });
    expect(screen.getByTestId("agent-test-send")).toBeEnabled();
  });
});
