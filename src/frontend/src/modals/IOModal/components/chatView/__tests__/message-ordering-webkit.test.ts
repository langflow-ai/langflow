import sortPlaygroundMessages from "@/components/core/playgroundComponent/chat-view/chat-messages/utils/sort-sender-messages";
import type { ChatMessageType } from "../../../../../types/chat";
import sortIOModalMessages from "../helpers/sort-sender-messages";

/**
 * WebKit (Safari, and the WKWebView used by the desktop app) returns
 * Invalid Date for the backend's "%Y-%m-%d %H:%M:%S.%f %Z" timestamp format,
 * unlike V8 (Chrome, Node, jest). A raw `new Date(timestamp)` in the sort
 * comparators therefore yields NaN, Array.prototype.sort treats the NaN
 * comparison as 0, and the chat renders in cache-insertion order — putting
 * the AI answer above the user's question.
 */

const createMessage = (
  id: string,
  timestamp: string,
  isSend: boolean,
): ChatMessageType =>
  ({
    id,
    timestamp,
    isSend,
    message: "test message",
    sender_name: isSend ? "User" : "AI",
    session: "session-test",
    files: [],
    edit: false,
    category: "message",
    content_blocks: [],
  }) as unknown as ChatMessageType;

const RealDate = globalThis.Date;

// Must be a function constructor: `class extends Date` breaks under the ES5
// transpilation used by the test toolchain.
function WebKitLikeDate(value?: string | number | Date): Date {
  if (typeof value === "string" && value.trimEnd().endsWith(" UTC")) {
    return new RealDate(Number.NaN);
  }
  return value === undefined ? new RealDate() : new RealDate(value);
}

describe("Message ordering under WebKit", () => {
  beforeEach(() => {
    globalThis.Date = WebKitLikeDate as unknown as DateConstructor;
  });

  afterEach(() => {
    globalThis.Date = RealDate;
  });

  const comparators: Array<
    [string, (a: ChatMessageType, b: ChatMessageType) => number]
  > = [
    ["playground", sortPlaygroundMessages],
    ["IOModal", sortIOModalMessages],
  ];

  it.each(comparators)(
    "%s sort orders user before AI for backend UTC timestamps",
    (_name, sorter) => {
      const ai = createMessage("ai", "2026-07-24 15:05:52.571339 UTC", false);
      const user = createMessage(
        "user",
        "2026-07-24 15:05:48.123456 UTC",
        true,
      );

      const sorted = [ai, user].sort(sorter);

      expect(sorted.map((message) => message.id)).toEqual(["user", "ai"]);
    },
  );

  it.each(comparators)(
    "%s sort orders user before AI on identical backend UTC timestamps",
    (_name, sorter) => {
      const ai = createMessage("ai", "2026-07-24 15:05:48.571339 UTC", false);
      const user = createMessage(
        "user",
        "2026-07-24 15:05:48.571339 UTC",
        true,
      );

      const sorted = [ai, user].sort(sorter);

      expect(sorted.map((message) => message.id)).toEqual(["user", "ai"]);
    },
  );

  it.each(comparators)(
    "%s sort keeps chronological order across seconds",
    (_name, sorter) => {
      const first = createMessage(
        "first",
        "2026-07-24 15:05:48.000000 UTC",
        true,
      );
      const second = createMessage(
        "second",
        "2026-07-24 15:05:49.000000 UTC",
        false,
      );
      const third = createMessage(
        "third",
        "2026-07-24 15:05:50.000000 UTC",
        true,
      );

      const sorted = [third, first, second].sort(sorter);

      expect(sorted.map((message) => message.id)).toEqual([
        "first",
        "second",
        "third",
      ]);
    },
  );
});
