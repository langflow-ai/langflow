import { act, renderHook, waitFor } from "@testing-library/react";

import type {
  CollaborationOperationAcceptedMessage,
  CollaborationOperationBroadcastMessage,
} from "@/types/flow-collaboration";

import { useFlowCollaboration } from "../use-flow-collaboration";

type MockWebSocketInstance = {
  url: string;
  readyState: number;
  onopen: (() => void) | null;
  onmessage: ((event: MessageEvent) => void) | null;
  onerror: (() => void) | null;
  onclose: (() => void) | null;
  sent: string[];
  close: jest.Mock;
  triggerOpen: () => void;
  triggerMessage: (payload: unknown) => void;
  triggerClose: () => void;
};

const instances: MockWebSocketInstance[] = [];

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  readyState = MockWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  sent: string[] = [];
  close = jest.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  });

  constructor(url: string) {
    this.url = url;
    const instance: MockWebSocketInstance = {
      url,
      readyState: this.readyState,
      onopen: this.onopen,
      onmessage: this.onmessage,
      onerror: this.onerror,
      onclose: this.onclose,
      sent: this.sent,
      close: this.close,
      triggerOpen: () => {
        this.readyState = MockWebSocket.OPEN;
        this.onopen?.();
      },
      triggerMessage: (payload: unknown) => {
        this.onmessage?.({
          data: JSON.stringify(payload),
        } as MessageEvent);
      },
      triggerClose: () => {
        this.close();
      },
    };
    instances.push(instance);
  }

  send(data: string) {
    this.sent.push(data);
  }
}

jest.mock("@/hooks/flows/flow-collaboration-url", () => ({
  buildFlowCollaborationWebSocketUrl: (flowId: string) =>
    `ws://localhost/api/v1/flows/${flowId}/collab`,
}));

function latestSocket(): MockWebSocketInstance {
  const socket = instances.at(-1);
  if (!socket) {
    throw new Error("No mock WebSocket instance");
  }
  return socket;
}

type MountHookOptions = Partial<Parameters<typeof useFlowCollaboration>[0]> & {
  flowId?: string | undefined;
};

async function mountHook(options: MountHookOptions = {}) {
  const flowId = "flowId" in options ? options.flowId : "flow-1";
  const { enabled = true, ...callbacks } = options;
  const onRemoteOperation = jest.fn();
  const onReloadRequired = jest.fn();
  const onSessionError = jest.fn();

  const hook = renderHook(
    ({ id, isEnabled }: { id: string | undefined; isEnabled: boolean }) =>
      useFlowCollaboration({
        flowId: id,
        enabled: isEnabled,
        onRemoteOperation,
        onReloadRequired,
        onSessionError,
        ...callbacks,
      }),
    { initialProps: { id: flowId, isEnabled: enabled } },
  );

  await act(async () => {});

  return { ...hook, onRemoteOperation, onReloadRequired, onSessionError };
}

async function connectSession(currentRevision = 0) {
  const socket = latestSocket();
  await act(async () => {
    socket.triggerOpen();
  });
  expect(JSON.parse(socket.sent[0]!)).toEqual({ type: "session.start" });

  await act(async () => {
    socket.triggerMessage({
      type: "session.ready",
      connection_id: "conn-1",
      flow_id: "flow-1",
      current_revision: currentRevision,
      users: [
        {
          user_id: "user-1",
          username: "ana",
          profile_image: "Space/046-rocket.svg",
        },
      ],
    });
  });

  return socket;
}

describe("useFlowCollaboration", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    instances.length = 0;
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
  });

  it("should not open a socket when flowId is undefined", async () => {
    await mountHook({ flowId: undefined });

    expect(instances).toHaveLength(0);
  });

  it("should open the socket, send session.start, and become ready on session.ready", async () => {
    const { result } = await mountHook({ flowId: "flow-1" });

    expect(latestSocket().url).toBe(
      "ws://localhost/api/v1/flows/flow-1/collab",
    );
    expect(result.current.status).toBe("connecting");

    await connectSession(12);

    expect(result.current.status).toBe("ready");
    expect(result.current.connectionId).toBe("conn-1");
    expect(result.current.currentRevision).toBe(12);
    expect(result.current.users).toEqual([
      {
        user_id: "user-1",
        username: "ana",
        profile_image: "Space/046-rocket.svg",
      },
    ]);
    expect(result.current.isReady).toBe(true);
  });

  it("should submit operation.submit with the current revision", async () => {
    const { result } = await mountHook({ flowId: "flow-1" });
    const socket = await connectSession(5);

    let acceptedMessage: CollaborationOperationAcceptedMessage | undefined;
    await act(async () => {
      const promise = result.current.submitOperations([
        { type: "update_nodes", nodes: [{ id: "n1" } as never] },
      ]);
      const submit = JSON.parse(socket.sent[1]!) as {
        request_id: string;
        type: string;
        base_revision: number;
        operations: unknown[];
      };
      expect(submit.type).toBe("operation.submit");
      expect(submit.base_revision).toBe(5);
      expect(submit.operations).toHaveLength(1);

      socket.triggerMessage({
        type: "operation.accepted",
        request_id: submit.request_id,
        flow_id: "flow-1",
        revision: 6,
        actor_user_id: "user-1",
        actor_delegate: "self",
        forward_ops: submit.operations,
        created_at: "2026-05-30T00:00:00Z",
      });
      acceptedMessage = await promise;
    });

    expect(socket.sent).toHaveLength(2);
    expect(acceptedMessage).toMatchObject({
      type: "operation.accepted",
      revision: 6,
    });
    expect(result.current.currentRevision).toBe(6);
  });

  it("should treat operation.accepted with a matching request_id as acknowledgement only", async () => {
    const { result, onRemoteOperation } = await mountHook({ flowId: "flow-1" });
    const socket = await connectSession(3);

    await act(async () => {
      const promise = result.current.submitOperations([
        { type: "delete_edges", ids: ["e1"] },
      ]);
      const submit = JSON.parse(socket.sent.at(-1)!);
      socket.triggerMessage({
        type: "operation.accepted",
        request_id: submit.request_id,
        flow_id: "flow-1",
        revision: 4,
        actor_user_id: "user-1",
        actor_delegate: "self",
        forward_ops: [{ type: "delete_edges", ids: ["e1"] }],
        created_at: "2026-05-30T00:00:00Z",
      });
      await promise;
    });

    expect(onRemoteOperation).not.toHaveBeenCalled();
  });

  it("should apply remote operation.broadcast messages and advance revision", async () => {
    const { onRemoteOperation } = await mountHook({ flowId: "flow-1" });
    await connectSession(7);

    const broadcast: CollaborationOperationBroadcastMessage = {
      type: "operation.broadcast",
      flow_id: "flow-1",
      revision: 8,
      actor_user_id: "user-2",
      actor_delegate: "self",
      forward_ops: [{ type: "add_nodes", nodes: [{ id: "n2" } as never] }],
      created_at: "2026-05-30T00:00:01Z",
    };

    await act(async () => {
      latestSocket().triggerMessage(broadcast);
    });

    expect(onRemoteOperation).toHaveBeenCalledWith(broadcast);
  });

  it("should request reload on revision gap for operation.broadcast", async () => {
    const { result, onReloadRequired } = await mountHook({ flowId: "flow-1" });
    await connectSession(10);

    await act(async () => {
      latestSocket().triggerMessage({
        type: "operation.broadcast",
        flow_id: "flow-1",
        revision: 15,
        actor_user_id: "user-2",
        actor_delegate: "self",
        forward_ops: [],
        created_at: "2026-05-30T00:00:01Z",
      });
    });

    expect(onReloadRequired).toHaveBeenCalledWith(
      "revision_gap",
      expect.objectContaining({
        expectedRevision: 11,
        receivedRevision: 15,
      }),
    );
    expect(result.current.currentRevision).toBe(10);
    expect(onReloadRequired).not.toHaveBeenCalledWith("stale_revision");
  });

  it("should request reload on stale revision rejection", async () => {
    const { result, onReloadRequired } = await mountHook({ flowId: "flow-1" });
    const socket = await connectSession(8);

    await act(async () => {
      const promise = result.current.submitOperations([
        { type: "update_metadata", fields: { foo: "bar" } },
      ]);
      const submit = JSON.parse(socket.sent.at(-1)!);
      socket.triggerMessage({
        type: "operation.rejected",
        request_id: submit.request_id,
        status: 409,
        detail: "Stale base revision",
        current_revision: 12,
      });
      await expect(promise).rejects.toThrow("Stale base revision");
    });

    expect(onReloadRequired).toHaveBeenCalledWith(
      "stale_revision",
      expect.objectContaining({
        status: 409,
        currentRevision: 12,
      }),
    );
    expect(result.current.currentRevision).toBe(12);
  });

  it("should update presence roster on presence.updated", async () => {
    const { result } = await mountHook({ flowId: "flow-1" });
    await connectSession(0);

    await act(async () => {
      latestSocket().triggerMessage({
        type: "presence.updated",
        users: [
          { user_id: "user-1", username: "ana" },
          { user_id: "user-2", username: "bob", profile_image: null },
        ],
      });
    });

    expect(result.current.users).toHaveLength(2);
  });

  it("should request reload when the socket closes unexpectedly", async () => {
    const { onReloadRequired } = await mountHook({ flowId: "flow-1" });
    const socket = await connectSession(2);

    await act(async () => {
      socket.triggerClose();
    });

    await waitFor(() => {
      expect(onReloadRequired).toHaveBeenCalledWith("socket_closed", undefined);
    });
  });

  it("should reject submitOperations when the session is not ready", async () => {
    const { result } = await mountHook({ flowId: "flow-1" });

    await expect(
      result.current.submitOperations([{ type: "delete_nodes", ids: ["n1"] }]),
    ).rejects.toThrow("Collaboration session is not ready");
  });
});
