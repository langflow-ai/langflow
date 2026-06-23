import { queryClient } from "@/contexts";
import { useMessagesStore } from "@/stores/messagesStore";
import type { Message } from "@/types/messages";
import {
  findHumanInputContent,
  markHumanInputSubmitted,
} from "../human-input-card";

function makeCardMessage(requestId: string): Message {
  return {
    id: `human-input-${requestId}`,
    flow_id: "flow-1",
    text: "",
    sender: "Machine",
    sender_name: "AI",
    session_id: "flow-1",
    timestamp: new Date().toISOString(),
    files: [],
    edit: false,
    background_color: "",
    text_color: "",
    content_blocks: [
      {
        title: "Human input required",
        contents: [
          {
            type: "human_input",
            kind: "node_input",
            request_id: requestId,
            options: [
              { action_id: "approve", label: "Approve" },
              { action_id: "reject", label: "Reject" },
            ],
            allowed_decisions: ["approve", "reject"],
            job_id: "job-1",
          },
        ],
        allow_markdown: true,
        component: "HumanInput",
      },
    ],
  } as unknown as Message;
}

describe("markHumanInputSubmitted", () => {
  const requestId = "HumanInput-abc:run-1";
  const messageId = `human-input-${requestId}`;

  beforeEach(() => {
    queryClient.clear();
    useMessagesStore.getState().setMessages([]);
  });

  it("stamps submitted_action in BOTH the react-query cache and useMessagesStore", () => {
    const message = makeCardMessage(requestId);
    // Mirror injectHumanInputCard's dual write: the new playground reads the react-query
    // cache, the legacy IOModal playground reads useMessagesStore.
    queryClient.setQueryData(["useGetMessagesQuery", "flow-1"], [message]);
    useMessagesStore.getState().setMessages([message]);

    markHumanInputSubmitted(requestId, "approve");

    const cached = queryClient.getQueryData<Message[]>([
      "useGetMessagesQuery",
      "flow-1",
    ])!;
    expect(
      findHumanInputContent(cached[0].content_blocks)?.submitted_action,
    ).toBe("approve");

    const stored = useMessagesStore
      .getState()
      .messages.find((m) => m.id === messageId)!;
    expect(findHumanInputContent(stored.content_blocks)?.submitted_action).toBe(
      "approve",
    );
  });
});
