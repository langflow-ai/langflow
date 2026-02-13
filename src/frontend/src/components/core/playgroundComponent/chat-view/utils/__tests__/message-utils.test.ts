import { queryClient } from "@/contexts";
import type { Message } from "@/types/messages";
import {
  clearSessionMessages,
  findLastBotMessage,
  updateMessageProperties,
} from "../message-utils";

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({ playgroundPage: false }),
  },
}));

jest.mock("@/utils/playground-storage", () => ({
  removePlaygroundSessionMessages: jest.fn(),
  savePlaygroundMessages: jest.fn(),
}));

const MESSAGES_QUERY_KEY = "useGetMessagesQuery";
const QUERY_KEY = [MESSAGES_QUERY_KEY, { id: "flow-1", session_id: "s1" }];

function buildMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: "msg-1",
    text: "hello",
    sender: "Machine",
    sender_name: "AI",
    session_id: "s1",
    flow_id: "flow-1",
    timestamp: new Date().toISOString(),
    files: [],
    ...overrides,
  } as Message;
}

beforeEach(() => {
  queryClient.clear();
});

describe("findLastBotMessage", () => {
  it("should_return_last_bot_message_when_cache_has_messages", () => {
    const msg1 = buildMessage({ id: "m1", sender: "User" });
    const msg2 = buildMessage({ id: "m2", sender: "Machine" });
    const msg3 = buildMessage({ id: "m3", sender: "Machine" });

    queryClient.setQueryData(QUERY_KEY, [msg1, msg2, msg3]);

    const result = findLastBotMessage();

    expect(result).not.toBeNull();
    expect(result!.message.id).toBe("m3");
    expect(result!.queryKey).toEqual(QUERY_KEY);
  });

  it("should_return_null_when_no_bot_messages_exist", () => {
    const userMsg = buildMessage({ id: "m1", sender: "User" });
    queryClient.setQueryData(QUERY_KEY, [userMsg]);

    expect(findLastBotMessage()).toBeNull();
  });

  it("should_return_null_when_cache_is_empty", () => {
    expect(findLastBotMessage()).toBeNull();
  });

  it("should_skip_bot_messages_without_id", () => {
    const msgNoId = buildMessage({
      id: null as unknown as string,
      sender: "Machine",
    });
    const msgWithId = buildMessage({ id: "m2", sender: "Machine" });

    queryClient.setQueryData(QUERY_KEY, [msgNoId, msgWithId]);

    const result = findLastBotMessage();
    expect(result!.message.id).toBe("m2");
  });
});

describe("updateMessageProperties", () => {
  it("should_merge_new_properties_into_target_message", () => {
    const msg = buildMessage({
      id: "m1",
      properties: { state: "complete", source: { id: "s" } },
    });
    queryClient.setQueryData(QUERY_KEY, [msg]);

    updateMessageProperties("m1", QUERY_KEY, { build_duration: 1500 });

    const updated = queryClient.getQueryData<Message[]>(QUERY_KEY);
    expect(updated![0].properties).toEqual(
      expect.objectContaining({
        state: "complete",
        build_duration: 1500,
      }),
    );
  });

  it("should_not_modify_other_messages", () => {
    const msg1 = buildMessage({ id: "m1" });
    const msg2 = buildMessage({ id: "m2" });
    queryClient.setQueryData(QUERY_KEY, [msg1, msg2]);

    updateMessageProperties("m1", QUERY_KEY, { build_duration: 999 });

    const updated = queryClient.getQueryData<Message[]>(QUERY_KEY);
    expect(updated![1].properties).toEqual(msg2.properties);
  });

  it("should_handle_message_with_empty_properties", () => {
    const msg = buildMessage({ id: "m1", properties: {} });
    queryClient.setQueryData(QUERY_KEY, [msg]);

    updateMessageProperties("m1", QUERY_KEY, { build_duration: 500 });

    const updated = queryClient.getQueryData<Message[]>(QUERY_KEY);
    expect(updated![0].properties).toEqual(
      expect.objectContaining({ build_duration: 500 }),
    );
  });
});

describe("clearSessionMessages", () => {
  const FLOW_ID = "flow-1";
  const SESSION_ID = "custom-session";
  const MAIN_KEY = [MESSAGES_QUERY_KEY, { id: FLOW_ID }];
  const SESSION_KEY = [
    MESSAGES_QUERY_KEY,
    { id: FLOW_ID, session_id: SESSION_ID },
  ];

  it("should_clear_per_session_cache", () => {
    const msg = buildMessage({ id: "m1", session_id: SESSION_ID });
    queryClient.setQueryData(SESSION_KEY, [msg]);

    clearSessionMessages(SESSION_ID, FLOW_ID);

    const cached = queryClient.getQueryData<Message[]>(SESSION_KEY);
    expect(cached).toBeUndefined();
  });

  it("should_remove_non_default_session_messages_from_main_cache", () => {
    const sessionMsg = buildMessage({
      id: "m1",
      session_id: SESSION_ID,
      flow_id: FLOW_ID,
    });
    const otherMsg = buildMessage({
      id: "m2",
      session_id: "other-session",
      flow_id: FLOW_ID,
    });

    queryClient.setQueryData(MAIN_KEY, {
      rows: { data: [sessionMsg, otherMsg] },
    });

    clearSessionMessages(SESSION_ID, FLOW_ID);

    const mainCache = queryClient.getQueryData<{
      rows?: { data?: Message[] };
    }>(MAIN_KEY);
    expect(mainCache?.rows?.data).toHaveLength(1);
    expect(mainCache?.rows?.data![0].id).toBe("m2");
  });

  it("should_remove_default_session_messages_including_null_session_id", () => {
    const defaultMsg = buildMessage({
      id: "m1",
      session_id: FLOW_ID,
      flow_id: FLOW_ID,
    });
    const nullSessionMsg = buildMessage({
      id: "m2",
      session_id: null as unknown as string,
      flow_id: FLOW_ID,
    });
    const otherMsg = buildMessage({
      id: "m3",
      session_id: "other",
      flow_id: FLOW_ID,
    });

    queryClient.setQueryData(MAIN_KEY, {
      rows: { data: [defaultMsg, nullSessionMsg, otherMsg] },
    });

    clearSessionMessages(FLOW_ID, FLOW_ID);

    const mainCache = queryClient.getQueryData<{
      rows?: { data?: Message[] };
    }>(MAIN_KEY);
    expect(mainCache?.rows?.data).toHaveLength(1);
    expect(mainCache?.rows?.data![0].id).toBe("m3");
  });

  it("should_preserve_messages_from_different_flow", () => {
    const sameFlowMsg = buildMessage({
      id: "m1",
      session_id: SESSION_ID,
      flow_id: FLOW_ID,
    });
    const diffFlowMsg = buildMessage({
      id: "m2",
      session_id: SESSION_ID,
      flow_id: "other-flow",
    });

    queryClient.setQueryData(MAIN_KEY, {
      rows: { data: [sameFlowMsg, diffFlowMsg] },
    });

    clearSessionMessages(SESSION_ID, FLOW_ID);

    const mainCache = queryClient.getQueryData<{
      rows?: { data?: Message[] };
    }>(MAIN_KEY);
    expect(mainCache?.rows?.data).toHaveLength(1);
    expect(mainCache?.rows?.data![0].id).toBe("m2");
  });

  it("should_handle_missing_main_cache_gracefully", () => {
    queryClient.setQueryData(SESSION_KEY, [buildMessage()]);

    expect(() => clearSessionMessages(SESSION_ID, FLOW_ID)).not.toThrow();
  });
});
