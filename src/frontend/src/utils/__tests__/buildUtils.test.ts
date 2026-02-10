import { BuildStatus } from "@/constants/enums";

// --- Mocks ---

const mockFlowStoreState = {
  nodes: [] as any[],
  buildStartTime: null as number | null,
  stopNodeId: null as string | null,
  clearAndSetEdgesRunning: jest.fn(),
  setCurrentBuildingNodeId: jest.fn(),
  updateBuildStatus: jest.fn(),
  setBuildStartTime: jest.fn(),
};

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => mockFlowStoreState,
  },
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      setErrorData: jest.fn(),
    }),
  },
}));

jest.mock("@/controllers/API/api", () => ({
  api: { put: jest.fn(() => Promise.resolve()) },
  performStreamingRequest: jest.fn(),
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/messages"),
}));

const mockFindLastBotMessage = jest.fn(() => null);
const mockUpdateMessageProperties = jest.fn();
jest.mock(
  "@/components/core/playgroundComponent/chat-view/utils/message-utils",
  () => ({
    findLastBotMessage: (...args: any[]) => mockFindLastBotMessage(...args),
    updateMessageProperties: (...args: any[]) =>
      mockUpdateMessageProperties(...args),
  }),
);

jest.mock(
  "@/components/core/playgroundComponent/chat-view/utils/message-event-handler",
  () => ({
    handleMessageEvent: jest.fn(() => true),
  }),
);

const mockIsErrorLogType = jest.fn(() => false);
jest.mock("@/types/utils/typeCheckingUtils", () => ({
  isErrorLogType: (...args: any[]) => mockIsErrorLogType(...args),
}));

const mockIsOutputType = jest.fn(() => false);
jest.mock("@/utils/reactflowUtils", () => ({
  isOutputType: (...args: any[]) => mockIsOutputType(...args),
}));

jest.mock("@/utils/utils", () => ({
  isStringArray: (arr: any) =>
    Array.isArray(arr) && arr.every((v: any) => typeof v === "string"),
  tryParseJson: jest.fn((s: string) => null),
}));

jest.mock("@/constants/alerts_constants", () => ({
  MISSED_ERROR_ALERT: "MISSED_ERROR_ALERT",
}));

jest.mock("@/constants/constants", () => ({
  POLLING_MESSAGES: {
    ENDPOINT_NOT_AVAILABLE: "ENDPOINT_NOT_AVAILABLE",
    STREAMING_NOT_SUPPORTED: "STREAMING_NOT_SUPPORTED",
  },
}));

jest.mock("@/customization/utils/custom-buildUtils", () => ({
  customBuildUrl: jest.fn(),
  customCancelBuildUrl: jest.fn(),
  customEventsUrl: jest.fn(),
}));

jest.mock("@/customization/utils/custom-poll-build-events", () => ({
  customPollBuildEvents: jest.fn(),
}));

jest.mock("@/customization/utils/get-fetch-credentials", () => ({
  getFetchCredentials: jest.fn(() => "same-origin"),
}));

jest.mock("@/controllers/API", () => ({
  getVerticesOrder: jest.fn(),
  postBuildVertex: jest.fn(),
}));

import {
  processEndVertexEvent,
  processBatchedEvents,
  BATCHABLE_EVENTS,
  BATCH_YIELD_MS,
} from "../buildUtils";

// --- Helpers ---

function createValidBuildData(id: string, nextVerticesIds?: string[]) {
  return {
    build_data: {
      id,
      valid: true,
      data: { outputs: {} },
      next_vertices_ids: nextVerticesIds ?? null,
    },
  };
}

function createInvalidBuildData(id: string) {
  return {
    build_data: {
      id,
      valid: false,
      data: {
        outputs: {
          output_0: {
            message: { errorMessage: "Something went wrong" },
          },
        },
      },
      next_vertices_ids: null,
    },
  };
}

// --- Tests ---

describe("BATCHABLE_EVENTS", () => {
  it("should contain end_vertex, build_start, and build_end", () => {
    expect(BATCHABLE_EVENTS.has("end_vertex")).toBe(true);
    expect(BATCHABLE_EVENTS.has("build_start")).toBe(true);
    expect(BATCHABLE_EVENTS.has("build_end")).toBe(true);
  });

  it("should not contain non-batchable events", () => {
    expect(BATCHABLE_EVENTS.has("vertices_sorted")).toBe(false);
    expect(BATCHABLE_EVENTS.has("token")).toBe(false);
    expect(BATCHABLE_EVENTS.has("end")).toBe(false);
    expect(BATCHABLE_EVENTS.has("error")).toBe(false);
    expect(BATCHABLE_EVENTS.has("add_message")).toBe(false);
  });
});

describe("BATCH_YIELD_MS", () => {
  it("should be a positive number", () => {
    expect(BATCH_YIELD_MS).toBeGreaterThan(0);
    expect(typeof BATCH_YIELD_MS).toBe("number");
  });
});

describe("processEndVertexEvent", () => {
  let onBuildUpdate: jest.Mock;
  let onBuildError: jest.Mock;
  let onBuildStart: jest.Mock;
  let buildResults: boolean[];

  beforeEach(() => {
    jest.clearAllMocks();
    onBuildUpdate = jest.fn();
    onBuildError = jest.fn();
    onBuildStart = jest.fn();
    buildResults = [];
    mockFlowStoreState.nodes = [];
    mockFlowStoreState.buildStartTime = null;
    mockFlowStoreState.stopNodeId = null;
    mockIsOutputType.mockReturnValue(false);
    mockIsErrorLogType.mockReturnValue(false);
    mockFindLastBotMessage.mockReturnValue(null);
  });

  it("should return true and push true for valid build data", () => {
    const data = createValidBuildData("node-1");
    const result = processEndVertexEvent(data, buildResults, {
      onBuildUpdate,
      onBuildError,
      onBuildStart,
    });

    expect(result).toBe(true);
    expect(buildResults).toEqual([true]);
  });

  it("should call onBuildUpdate with BUILT status on valid build", () => {
    const data = createValidBuildData("node-1");
    processEndVertexEvent(data, buildResults, {
      onBuildUpdate,
      onBuildError,
      onBuildStart,
    });

    expect(onBuildUpdate).toHaveBeenCalledWith(
      data.build_data,
      BuildStatus.BUILT,
      "",
    );
  });

  it("should return false and push false for invalid build data", () => {
    mockIsErrorLogType.mockReturnValue(true);
    const data = createInvalidBuildData("node-1");
    const result = processEndVertexEvent(data, buildResults, {
      onBuildUpdate,
      onBuildError,
      onBuildStart,
    });

    expect(result).toBe(false);
    expect(buildResults).toEqual([false]);
  });

  it("should call onBuildError with error messages on invalid build", () => {
    mockIsErrorLogType.mockReturnValue(true);
    const data = createInvalidBuildData("node-1");
    processEndVertexEvent(data, buildResults, {
      onBuildUpdate,
      onBuildError,
      onBuildStart,
    });

    expect(onBuildError).toHaveBeenCalledWith(
      "Error Building Component",
      ["Something went wrong"],
      [{ id: "node-1" }],
    );
  });

  it("should call onBuildUpdate with ERROR status on invalid build", () => {
    mockIsErrorLogType.mockReturnValue(true);
    const data = createInvalidBuildData("node-1");
    processEndVertexEvent(data, buildResults, {
      onBuildUpdate,
      onBuildError,
      onBuildStart,
    });

    expect(onBuildUpdate).toHaveBeenCalledWith(
      data.build_data,
      BuildStatus.ERROR,
      "",
    );
  });

  it("should call clearAndSetEdgesRunning with next vertex IDs", () => {
    const data = createValidBuildData("node-1", ["node-2", "node-3"]);
    processEndVertexEvent(data, buildResults, {
      onBuildUpdate,
      onBuildError,
      onBuildStart,
    });

    expect(mockFlowStoreState.clearAndSetEdgesRunning).toHaveBeenCalledWith([
      "node-2",
      "node-3",
    ]);
  });

  it("should call clearAndSetEdgesRunning with undefined when no next vertices", () => {
    const data = createValidBuildData("node-1");
    processEndVertexEvent(data, buildResults, {
      onBuildUpdate,
      onBuildError,
      onBuildStart,
    });

    expect(mockFlowStoreState.clearAndSetEdgesRunning).toHaveBeenCalledWith(
      undefined,
    );
  });

  it("should call setCurrentBuildingNodeId with next IDs", () => {
    const data = createValidBuildData("node-1", ["node-2"]);
    processEndVertexEvent(data, buildResults, {
      onBuildUpdate,
      onBuildError,
      onBuildStart,
    });

    expect(mockFlowStoreState.setCurrentBuildingNodeId).toHaveBeenCalledWith([
      "node-2",
    ]);
  });

  it("should update build status of next vertices to TO_BUILD", () => {
    const data = createValidBuildData("node-1", ["node-2", "node-3"]);
    processEndVertexEvent(data, buildResults, {
      onBuildUpdate,
      onBuildError,
      onBuildStart,
    });

    expect(mockFlowStoreState.updateBuildStatus).toHaveBeenCalledWith(
      ["node-2", "node-3"],
      BuildStatus.TO_BUILD,
    );
  });

  it("should call onBuildStart with mapped next vertices", () => {
    const data = createValidBuildData("node-1", ["node-2", "node-3"]);
    processEndVertexEvent(data, buildResults, {
      onBuildUpdate,
      onBuildError,
      onBuildStart,
    });

    expect(onBuildStart).toHaveBeenCalledWith([
      { id: "node-2", reference: "node-2" },
      { id: "node-3", reference: "node-3" },
    ]);
  });

  it("should track build duration for output type nodes", () => {
    mockIsOutputType.mockReturnValue(true);
    mockFlowStoreState.buildStartTime = Date.now() - 500;
    mockFlowStoreState.nodes = [{ id: "node-1", data: { type: "ChatOutput" } }];
    mockFindLastBotMessage.mockReturnValue({
      message: { id: "msg-1", properties: {} },
      queryKey: ["messages"],
    });

    const data = createValidBuildData("node-1");
    processEndVertexEvent(data, buildResults, {
      onBuildUpdate,
      onBuildError,
      onBuildStart,
    });

    expect(mockUpdateMessageProperties).toHaveBeenCalled();
    expect(mockFlowStoreState.setBuildStartTime).toHaveBeenCalled();
  });

  it("should not track duration when buildStartTime is null", () => {
    mockIsOutputType.mockReturnValue(true);
    mockFlowStoreState.buildStartTime = null;
    mockFlowStoreState.nodes = [{ id: "node-1", data: { type: "ChatOutput" } }];

    const data = createValidBuildData("node-1");
    processEndVertexEvent(data, buildResults, {
      onBuildUpdate,
      onBuildError,
      onBuildStart,
    });

    expect(mockUpdateMessageProperties).not.toHaveBeenCalled();
    expect(mockFlowStoreState.setBuildStartTime).not.toHaveBeenCalled();
  });

  it("should not call setCurrentBuildingNodeId when no next vertices", () => {
    const data = createValidBuildData("node-1");
    processEndVertexEvent(data, buildResults, {
      onBuildUpdate,
      onBuildError,
      onBuildStart,
    });

    expect(mockFlowStoreState.setCurrentBuildingNodeId).not.toHaveBeenCalled();
  });
});

describe("processBatchedEvents", () => {
  let buildResults: boolean[];
  let callbacks: {
    onBuildStart: jest.Mock;
    onBuildUpdate: jest.Mock;
    onBuildComplete: jest.Mock;
    onBuildError: jest.Mock;
    onGetOrderSuccess: jest.Mock;
    onValidateNodes: jest.Mock;
  };
  let onEventFallback: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    buildResults = [];
    callbacks = {
      onBuildStart: jest.fn(),
      onBuildUpdate: jest.fn(),
      onBuildComplete: jest.fn(),
      onBuildError: jest.fn(),
      onGetOrderSuccess: jest.fn(),
      onValidateNodes: jest.fn(),
    };
    onEventFallback = jest.fn(() => Promise.resolve(true));
    mockFlowStoreState.nodes = [];
    mockFlowStoreState.buildStartTime = null;
    mockFlowStoreState.stopNodeId = null;
    mockIsOutputType.mockReturnValue(false);
    mockIsErrorLogType.mockReturnValue(false);
  });

  it("should process end_vertex events via processEndVertexEvent", async () => {
    const events = [
      {
        event: "end_vertex",
        data: {
          build_data: {
            id: "node-1",
            valid: true,
            data: { outputs: {} },
            next_vertices_ids: null,
          },
        },
      },
    ];

    const result = await processBatchedEvents(
      events,
      buildResults,
      callbacks,
      onEventFallback,
    );

    expect(result).toBe(true);
    expect(buildResults).toEqual([true]);
    expect(callbacks.onBuildUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ id: "node-1", valid: true }),
      BuildStatus.BUILT,
      "",
    );
  });

  it("should handle build_start with data.id by updating status to BUILDING", async () => {
    const events = [{ event: "build_start", data: { id: "node-1" } }];

    const result = await processBatchedEvents(
      events,
      buildResults,
      callbacks,
      onEventFallback,
    );

    expect(result).toBe(true);
    expect(mockFlowStoreState.updateBuildStatus).toHaveBeenCalledWith(
      ["node-1"],
      BuildStatus.BUILDING,
    );
  });

  it("should handle build_start without data.id by setting buildStartTime", async () => {
    const events = [{ event: "build_start", data: {} }];

    const result = await processBatchedEvents(
      events,
      buildResults,
      callbacks,
      onEventFallback,
    );

    expect(result).toBe(true);
    expect(mockFlowStoreState.setBuildStartTime).toHaveBeenCalledWith(
      expect.any(Number),
    );
  });

  it("should handle build_end with data.id by updating status to BUILT", async () => {
    const events = [{ event: "build_end", data: { id: "node-1" } }];

    const result = await processBatchedEvents(
      events,
      buildResults,
      callbacks,
      onEventFallback,
    );

    expect(result).toBe(true);
    expect(mockFlowStoreState.updateBuildStatus).toHaveBeenCalledWith(
      ["node-1"],
      BuildStatus.BUILT,
    );
  });

  it("should process non-batchable events via onEvent callback", async () => {
    const events = [
      { event: "vertices_sorted", data: { ids: ["n1"], to_run: ["n1"] } },
    ];

    const result = await processBatchedEvents(
      events,
      buildResults,
      callbacks,
      onEventFallback,
    );

    expect(result).toBe(true);
    expect(onEventFallback).toHaveBeenCalledWith(
      "vertices_sorted",
      { ids: ["n1"], to_run: ["n1"] },
      buildResults,
      callbacks,
    );
  });

  it("should return false and stop on failed batchable event", async () => {
    mockIsErrorLogType.mockReturnValue(true);
    const events = [
      {
        event: "end_vertex",
        data: {
          build_data: {
            id: "node-1",
            valid: false,
            data: {
              outputs: {
                out: { message: { errorMessage: "fail" } },
              },
            },
            next_vertices_ids: null,
          },
        },
      },
      { event: "build_start", data: { id: "node-2" } },
    ];

    const result = await processBatchedEvents(
      events,
      buildResults,
      callbacks,
      onEventFallback,
    );

    expect(result).toBe(false);
    // Second event should not have been processed
    expect(mockFlowStoreState.updateBuildStatus).not.toHaveBeenCalledWith(
      ["node-2"],
      BuildStatus.BUILDING,
    );
  });

  it("should return false and stop on failed non-batchable event", async () => {
    onEventFallback.mockResolvedValueOnce(false);
    const events = [{ event: "error", data: { text: "something broke" } }];

    const result = await processBatchedEvents(
      events,
      buildResults,
      callbacks,
      onEventFallback,
    );

    expect(result).toBe(false);
  });

  it("should return true when all events succeed", async () => {
    const events = [
      { event: "build_start", data: {} },
      {
        event: "end_vertex",
        data: {
          build_data: {
            id: "node-1",
            valid: true,
            data: { outputs: {} },
            next_vertices_ids: null,
          },
        },
      },
      { event: "build_end", data: { id: "node-1" } },
    ];

    const result = await processBatchedEvents(
      events,
      buildResults,
      callbacks,
      onEventFallback,
    );

    expect(result).toBe(true);
  });

  it("should handle mixed batchable and non-batchable events", async () => {
    const events = [
      { event: "build_start", data: { id: "node-1" } },
      { event: "token", data: { chunk: "hello" } },
      {
        event: "end_vertex",
        data: {
          build_data: {
            id: "node-1",
            valid: true,
            data: { outputs: {} },
            next_vertices_ids: null,
          },
        },
      },
    ];

    const result = await processBatchedEvents(
      events,
      buildResults,
      callbacks,
      onEventFallback,
    );

    expect(result).toBe(true);
    expect(mockFlowStoreState.updateBuildStatus).toHaveBeenCalledWith(
      ["node-1"],
      BuildStatus.BUILDING,
    );
    expect(onEventFallback).toHaveBeenCalledWith(
      "token",
      { chunk: "hello" },
      buildResults,
      callbacks,
    );
    expect(buildResults).toEqual([true]);
  });

  it("should handle empty events array", async () => {
    const result = await processBatchedEvents(
      [],
      buildResults,
      callbacks,
      onEventFallback,
    );

    expect(result).toBe(true);
    expect(onEventFallback).not.toHaveBeenCalled();
    expect(mockFlowStoreState.updateBuildStatus).not.toHaveBeenCalled();
  });

  it("should handle build_start with null data.id by setting buildStartTime", async () => {
    const events = [{ event: "build_start", data: { id: null } }];

    const result = await processBatchedEvents(
      events,
      buildResults,
      callbacks,
      onEventFallback,
    );

    expect(result).toBe(true);
    expect(mockFlowStoreState.setBuildStartTime).toHaveBeenCalledWith(
      expect.any(Number),
    );
    expect(mockFlowStoreState.updateBuildStatus).not.toHaveBeenCalled();
  });
});
