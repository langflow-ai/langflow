import { queryClient } from "@/contexts";
import type { Message } from "@/types/messages";
import { findLastBotMessage, updateMessageProperties } from "../message-utils";

const QUERY_KEY = ["useGetMessagesQuery", { id: "flow-1", session_id: "s1" }];

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

  it("should_return_last_bot_message_for_given_flow_and_session_only", () => {
    const s1Key = ["useGetMessagesQuery", { id: "flow-1", session_id: "s1" }];
    const s2Key = ["useGetMessagesQuery", { id: "flow-1", session_id: "s2" }];
    const msgS1 = buildMessage({
      id: "m-s1",
      sender: "Machine",
      session_id: "s1",
    });
    const msgS2 = buildMessage({
      id: "m-s2",
      sender: "Machine",
      session_id: "s2",
    });

    queryClient.setQueryData(s1Key, [msgS1]);
    queryClient.setQueryData(s2Key, [msgS2]);

    const resultS1 = findLastBotMessage("flow-1", "s1");
    const resultS2 = findLastBotMessage("flow-1", "s2");

    expect(resultS1).not.toBeNull();
    expect(resultS1!.message.id).toBe("m-s1");
    expect(resultS2).not.toBeNull();
    expect(resultS2!.message.id).toBe("m-s2");
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
