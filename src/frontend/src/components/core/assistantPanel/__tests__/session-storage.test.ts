import type {
  AssistantMessage,
  SerializedAssistantMessage,
  SessionHistoryEntry,
} from "../assistant-panel.types";
import {
  deserializeMessages,
  loadSessionsFromStorage,
  saveSessionsToStorage,
  serializeMessages,
} from "../helpers/session-storage";

const TEST_STORAGE_KEY = "test-sessions";

const SAMPLE_TIMESTAMP = new Date("2026-03-20T10:00:00Z");
const SAMPLE_TIMESTAMP_ISO = "2026-03-20T10:00:00.000Z";

function createUserMessage(
  overrides?: Partial<AssistantMessage>,
): AssistantMessage {
  return {
    id: "msg-1",
    role: "user",
    content: "Create a component",
    timestamp: SAMPLE_TIMESTAMP,
    status: "complete",
    ...overrides,
  };
}

function createAssistantMessage(
  overrides?: Partial<AssistantMessage>,
): AssistantMessage {
  return {
    id: "msg-2",
    role: "assistant",
    content: "Here is your component",
    timestamp: SAMPLE_TIMESTAMP,
    status: "complete",
    result: {
      content: "response text",
      validated: true,
      className: "MyComponent",
      componentCode: "class MyComponent(Component): pass",
    },
    ...overrides,
  };
}

function createSessionEntry(
  overrides?: Partial<SessionHistoryEntry>,
): SessionHistoryEntry {
  return {
    sessionId: "session-1",
    firstUserMessage: "Create a component",
    messageCount: 2,
    lastActiveAt: SAMPLE_TIMESTAMP_ISO,
    messages: [],
    ...overrides,
  };
}

const store: Record<string, string> = {};
const localStorageMock: Storage = {
  getItem: (key: string) => store[key] ?? null,
  setItem: (key: string, value: string) => {
    store[key] = value;
  },
  removeItem: (key: string) => {
    delete store[key];
  },
  clear: () => {
    for (const key in store) delete store[key];
  },
  get length() {
    return Object.keys(store).length;
  },
  key: (index: number) => Object.keys(store)[index] ?? null,
};

Object.defineProperty(window, "localStorage", {
  value: localStorageMock,
  writable: true,
});

beforeEach(() => {
  localStorage.clear();
});

describe("serializeMessages", () => {
  it("should_convert_timestamp_to_iso_string", () => {
    const messages = [createUserMessage()];

    const result = serializeMessages(messages);

    expect(result[0].timestamp).toBe(SAMPLE_TIMESTAMP_ISO);
  });

  it("should_strip_progress_field", () => {
    const messages = [
      createAssistantMessage({
        progress: {
          step: "validating",
          attempt: 1,
          maxAttempts: 3,
        },
      }),
    ];

    const result = serializeMessages(messages);

    expect(result[0]).not.toHaveProperty("progress");
  });

  it("should_preserve_result_with_componentCode", () => {
    const messages = [createAssistantMessage()];

    const result = serializeMessages(messages);

    expect(result[0].result).toBeDefined();
    expect(result[0].result?.componentCode).toBe(
      "class MyComponent(Component): pass",
    );
    expect(result[0].result?.className).toBe("MyComponent");
    expect(result[0].result?.validated).toBe(true);
  });

  it("should_preserve_messages_without_result", () => {
    const messages = [createUserMessage()];

    const result = serializeMessages(messages);

    expect(result[0].result).toBeUndefined();
    expect(result[0].content).toBe("Create a component");
  });

  it("should_mark_streaming_messages_as_cancelled", () => {
    const messages = [
      createAssistantMessage({ status: "streaming", content: "" }),
    ];

    const result = serializeMessages(messages);

    expect(result[0].status).toBe("cancelled");
  });

  it("should_mark_pending_messages_as_cancelled", () => {
    const messages = [createUserMessage({ status: "pending" })];

    const result = serializeMessages(messages);

    expect(result[0].status).toBe("cancelled");
  });

  it("should_preserve_complete_status", () => {
    const messages = [createUserMessage({ status: "complete" })];

    const result = serializeMessages(messages);

    expect(result[0].status).toBe("complete");
  });

  it("should_handle_empty_array", () => {
    expect(serializeMessages([])).toEqual([]);
  });
});

describe("deserializeMessages", () => {
  it("should_convert_iso_string_back_to_date", () => {
    const serialized: SerializedAssistantMessage[] = [
      {
        id: "1",
        role: "user",
        content: "hi",
        timestamp: SAMPLE_TIMESTAMP_ISO,
        status: "complete",
      },
    ];

    const result = deserializeMessages(serialized);

    expect(result[0].timestamp).toBeInstanceOf(Date);
    expect(result[0].timestamp.toISOString()).toBe(SAMPLE_TIMESTAMP_ISO);
  });

  it("should_preserve_result_without_componentCode", () => {
    const serialized: SerializedAssistantMessage[] = [
      {
        id: "2",
        role: "assistant",
        content: "done",
        timestamp: SAMPLE_TIMESTAMP_ISO,
        status: "complete",
        result: { content: "text", validated: true, className: "Foo" },
      },
    ];

    const result = deserializeMessages(serialized);

    expect(result[0].result?.className).toBe("Foo");
    expect(result[0].result?.validated).toBe(true);
  });

  it("should_handle_empty_array", () => {
    expect(deserializeMessages([])).toEqual([]);
  });
});

describe("loadSessionsFromStorage", () => {
  it("should_return_empty_array_when_no_data", () => {
    expect(loadSessionsFromStorage(TEST_STORAGE_KEY)).toEqual([]);
  });

  it("should_return_parsed_sessions", () => {
    const sessions = [createSessionEntry()];
    localStorage.setItem(TEST_STORAGE_KEY, JSON.stringify(sessions));

    const result = loadSessionsFromStorage(TEST_STORAGE_KEY);

    expect(result).toHaveLength(1);
    expect(result[0].sessionId).toBe("session-1");
  });

  it("should_return_empty_array_on_invalid_json", () => {
    localStorage.setItem(TEST_STORAGE_KEY, "not json");

    expect(loadSessionsFromStorage(TEST_STORAGE_KEY)).toEqual([]);
  });

  it("should_return_empty_array_when_stored_value_is_not_array", () => {
    localStorage.setItem(TEST_STORAGE_KEY, JSON.stringify({ not: "array" }));

    expect(loadSessionsFromStorage(TEST_STORAGE_KEY)).toEqual([]);
  });
});

describe("saveSessionsToStorage", () => {
  it("should_persist_sessions_to_localStorage", () => {
    const sessions = [createSessionEntry()];

    saveSessionsToStorage(TEST_STORAGE_KEY, sessions);

    const stored = JSON.parse(localStorage.getItem(TEST_STORAGE_KEY) || "[]");
    expect(stored).toHaveLength(1);
    expect(stored[0].sessionId).toBe("session-1");
  });

  it("should_overwrite_existing_data", () => {
    localStorage.setItem(
      TEST_STORAGE_KEY,
      JSON.stringify([createSessionEntry()]),
    );

    saveSessionsToStorage(TEST_STORAGE_KEY, []);

    const stored = JSON.parse(localStorage.getItem(TEST_STORAGE_KEY) || "[]");
    expect(stored).toEqual([]);
  });
});

describe("serialize_deserialize_roundtrip", () => {
  it("should_preserve_message_data_through_roundtrip", () => {
    const original = [createUserMessage(), createAssistantMessage()];

    const serialized = serializeMessages(original);
    const restored = deserializeMessages(serialized);

    expect(restored).toHaveLength(2);
    expect(restored[0].content).toBe("Create a component");
    expect(restored[0].timestamp.toISOString()).toBe(SAMPLE_TIMESTAMP_ISO);
    expect(restored[1].result?.className).toBe("MyComponent");
    expect(restored[1].result?.componentCode).toBe(
      "class MyComponent(Component): pass",
    );
  });
});
