import { useStartConversation } from "../use-start-conversation";

class FakeWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static instances: FakeWebSocket[] = [];

  readyState = FakeWebSocket.OPEN;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onopen: (() => void) | null = null;
  close = jest.fn();
  send = jest.fn();

  constructor(public readonly url: string) {
    FakeWebSocket.instances.push(this);
  }
}

describe("useStartConversation", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    Object.defineProperty(globalThis, "WebSocket", {
      configurable: true,
      value: FakeWebSocket,
    });
  });

  it("ignores a stale socket close after a replacement is active", () => {
    const wsRef = { current: null as WebSocket | null };
    const stopRecording = jest.fn();
    const commonArgs = [
      wsRef,
      jest.fn(),
      jest.fn(),
      jest.fn(),
      stopRecording,
      "session-1",
    ] as const;

    useStartConversation("flow-a", ...commonArgs);
    const firstSocket = FakeWebSocket.instances[0];
    useStartConversation("flow-b", ...commonArgs);
    const secondSocket = FakeWebSocket.instances[1];

    firstSocket.onclose?.({ code: 1000 } as CloseEvent);

    expect(wsRef.current).toBe(secondSocket);
    expect(stopRecording).not.toHaveBeenCalled();
  });

  it("closes and detaches the active socket after an error", () => {
    const wsRef = { current: null as WebSocket | null };
    const setStatus = jest.fn();
    const stopRecording = jest.fn();

    useStartConversation(
      "flow-a",
      wsRef,
      setStatus,
      jest.fn(),
      jest.fn(),
      stopRecording,
      "session-1",
    );
    const socket = FakeWebSocket.instances[0];

    socket.onerror?.(new Event("error"));

    expect(stopRecording).toHaveBeenCalledTimes(1);
    expect(wsRef.current).toBeNull();
    expect(socket.close).toHaveBeenCalledTimes(1);
    expect(socket.onerror).toBeNull();
    expect(socket.onclose).toBeNull();
  });
});
