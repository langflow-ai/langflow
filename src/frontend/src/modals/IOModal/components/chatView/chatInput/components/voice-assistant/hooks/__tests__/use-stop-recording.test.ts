import { useStopRecording } from "../use-stop-recording";

describe("useStopRecording", () => {
  it("detaches an old socket before closing it", () => {
    const socket = {
      close: jest.fn(),
      onclose: jest.fn(),
      onerror: jest.fn(),
      onmessage: jest.fn(),
      onopen: jest.fn(),
    } as unknown as WebSocket;
    const wsRef = {
      current: socket,
    };
    const setIsRecording = jest.fn();

    useStopRecording(
      { current: null },
      { current: null },
      { current: null },
      wsRef,
      { current: null },
      setIsRecording,
    );

    expect(wsRef.current).toBeNull();
    expect(socket.onclose).toBeNull();
    expect(socket.onerror).toBeNull();
    expect(socket.onmessage).toBeNull();
    expect(socket.onopen).toBeNull();
    expect(socket.close).toHaveBeenCalledTimes(1);
    expect(setIsRecording).toHaveBeenCalledWith(false);
  });
});
