import { queryClient } from "@/contexts";
import { useMessagesStore } from "@/stores/messagesStore";
import type { Message } from "@/types/messages";
import {
  findHumanInputContent,
  injectHumanInputCard,
  isHumanInputCardAnswered,
  markHumanInputSubmitted,
} from "../human-input-card";

function makeCardMessage(
  requestId: string,
  overrides?: { id?: string; submitted_action?: string },
): Message {
  return {
    id: overrides?.id ?? `human-input-${requestId}`,
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
            ...(overrides?.submitted_action
              ? { submitted_action: overrides.submitted_action }
              : {}),
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

  it("stamps a card reloaded from the DB (database UUID id, not the synthetic one)", () => {
    // After a page reload the persisted card comes back with its database id;
    // the stamp must land by matching the nested human_input request_id.
    const persisted = makeCardMessage(requestId, {
      id: "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
    });
    queryClient.setQueryData(["useGetMessagesQuery", "flow-1"], [persisted]);
    useMessagesStore.getState().setMessages([persisted]);

    markHumanInputSubmitted(requestId, "reject");

    const cached = queryClient.getQueryData<Message[]>([
      "useGetMessagesQuery",
      "flow-1",
    ])!;
    expect(
      findHumanInputContent(cached[0].content_blocks)?.submitted_action,
    ).toBe("reject");
  });
});

describe("isHumanInputCardAnswered", () => {
  const requestId = "HumanInput-abc:run-1";

  beforeEach(() => {
    queryClient.clear();
    useMessagesStore.getState().setMessages([]);
  });

  it("recognizes an answered card persisted with a database id after reload", () => {
    const persisted = makeCardMessage(requestId, {
      id: "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
      submitted_action: "approve",
    });
    queryClient.setQueryData(["useGetMessagesQuery", "flow-1"], [persisted]);

    expect(isHumanInputCardAnswered({ request_id: requestId }, "job-1")).toBe(
      true,
    );
  });

  it("does not treat a different, unanswered pause as answered", () => {
    const persisted = makeCardMessage(requestId, {
      id: "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
      submitted_action: "approve",
    });
    queryClient.setQueryData(["useGetMessagesQuery", "flow-1"], [persisted]);

    expect(
      isHumanInputCardAnswered(
        { request_id: "HumanInput-other:run-1" },
        "job-1",
      ),
    ).toBe(false);
  });
});

describe("injectHumanInputCard", () => {
  const requestId = "HumanInput-abc:run-1";
  const payload = {
    request_id: requestId,
    kind: "node_input",
    prompt: "Approve?",
    options: [{ action_id: "approve", label: "Approve" }],
    allowed_decisions: ["approve"],
  };
  const opts = { flowId: "flow-1", threadId: "flow-1" } as Parameters<
    typeof injectHumanInputCard
  >[2];

  beforeEach(() => {
    queryClient.clear();
    useMessagesStore.getState().setMessages([]);
  });

  function cardsInCache(): Message[] {
    const messages =
      queryClient.getQueryData<Message[]>([
        "useGetMessagesQuery",
        { id: "flow-1", session_id: "flow-1" },
      ]) ?? [];
    return messages.filter(
      (m) => findHumanInputContent(m.content_blocks)?.request_id === requestId,
    );
  }

  it("does not inject a duplicate when the persisted unanswered card is already visible", () => {
    // The replay of a pending pause re-enters injection while the DB card (database
    // UUID id) is already in the cache — the box must not be duplicated.
    const persisted = makeCardMessage(requestId, {
      id: "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
    });
    queryClient.setQueryData(
      ["useGetMessagesQuery", { id: "flow-1", session_id: "flow-1" }],
      [persisted],
    );

    injectHumanInputCard(payload, "job-1", opts);

    expect(cardsInCache()).toHaveLength(1);
    expect(cardsInCache()[0].id).toBe("0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d");
  });

  it("injects the synthetic card when no card for the pause is visible yet", () => {
    injectHumanInputCard(payload, "job-1", opts);

    expect(cardsInCache()).toHaveLength(1);
    expect(cardsInCache()[0].id).toBe(`human-input-${requestId}`);
  });
});
