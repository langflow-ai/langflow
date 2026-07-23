/**
 * After approving the first of two sequential Human Input steps, the second approval card is
 * appended as a Machine message — it must force the chat to scroll (like a user send does),
 * or the run looks stuck below the fold.
 */

import type { ChatMessageType } from "@/types/chat";
import { shouldForceScrollOnNewMessage } from "../should-force-scroll";

const base: ChatMessageType = {
  id: "m1",
  message: "",
  isSend: false,
  sender_name: "AI",
  timestamp: new Date().toISOString(),
};

const humanInputCard = (submitted_action?: string): ChatMessageType => ({
  ...base,
  id: "human-input-HI2:job-1",
  content_blocks: [
    {
      title: "Human input required",
      contents: [
        {
          type: "human_input",
          kind: "node_input",
          request_id: "HI2:job-1",
          options: [{ action_id: "approve", label: "Approve" }],
          allowed_decisions: ["approve"],
          ...(submitted_action ? { submitted_action } : {}),
        },
      ],
    },
  ] as ChatMessageType["content_blocks"],
});

describe("shouldForceScrollOnNewMessage", () => {
  it("should scroll for a user send", () => {
    expect(shouldForceScrollOnNewMessage({ ...base, isSend: true })).toBe(true);
  });

  it("should NOT scroll for a plain bot message (stick-to-bottom owns that)", () => {
    expect(shouldForceScrollOnNewMessage(base)).toBe(false);
  });

  it("should scroll for a new unanswered human-input card (2nd approval must be visible)", () => {
    expect(shouldForceScrollOnNewMessage(humanInputCard())).toBe(true);
  });

  it("should NOT scroll for an already-answered card (reattach replay)", () => {
    expect(shouldForceScrollOnNewMessage(humanInputCard("approve"))).toBe(
      false,
    );
  });

  it("should NOT scroll for undefined", () => {
    expect(shouldForceScrollOnNewMessage(undefined)).toBe(false);
  });
});
