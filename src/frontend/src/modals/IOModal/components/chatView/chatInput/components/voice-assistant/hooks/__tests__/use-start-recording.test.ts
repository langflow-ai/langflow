import { useStartRecording } from "../use-start-recording";

// The worklet must reach `addModule` as a packaged URL. Building it from a
// Blob at runtime needs `script-src blob:`, which any strict CSP refuses, and
// it leaks an object URL on every failed start.
describe("useStartRecording", () => {
  const makeRef = <T>(current: T) => ({ current });

  const makeAudioContext = () => ({
    audioWorklet: { addModule: jest.fn().mockResolvedValue(undefined) },
    createMediaStreamSource: jest.fn(() => ({ connect: jest.fn() })),
    createAnalyser: jest.fn(() => ({ fftSize: 0, connect: jest.fn() })),
    destination: {},
  });

  const start = (audioContext: ReturnType<typeof makeAudioContext>) =>
    useStartRecording(
      makeRef(audioContext) as never,
      makeRef(null) as never,
      makeRef(null) as never,
      makeRef(null) as never,
      makeRef(null) as never,
      jest.fn(),
      jest.fn(),
      makeRef(false) as never,
      makeRef([]) as never,
      "/assets/audio-worklet-processor-abc123.js",
      makeRef(null) as never,
      jest.fn(),
    );

  beforeEach(() => {
    jest.clearAllMocks();
    Object.defineProperty(globalThis, "navigator", {
      configurable: true,
      value: {
        mediaDevices: {
          getUserMedia: jest
            .fn()
            .mockResolvedValue({ getTracks: () => [{ stop: jest.fn() }] }),
        },
      },
    });
    (globalThis as { AudioWorkletNode?: unknown }).AudioWorkletNode = jest.fn(
      () => ({ connect: jest.fn(), port: { onmessage: null } }),
    );
    globalThis.URL.createObjectURL = jest.fn();
  });

  it("loads the worklet from the packaged URL it was given", async () => {
    const audioContext = makeAudioContext();

    await start(audioContext);

    expect(audioContext.audioWorklet.addModule).toHaveBeenCalledWith(
      "/assets/audio-worklet-processor-abc123.js",
    );
  });

  it("never builds the worklet from a Blob URL", async () => {
    await start(makeAudioContext());

    expect(globalThis.URL.createObjectURL).not.toHaveBeenCalled();
  });

  it("stores the media stream so stopping releases the microphone", async () => {
    const audioContext = makeAudioContext();
    const mediaStreamRef = makeRef<MediaStream | null>(null);

    await useStartRecording(
      makeRef(audioContext) as never,
      makeRef(null) as never,
      makeRef(null) as never,
      makeRef(null) as never,
      mediaStreamRef as never,
      jest.fn(),
      jest.fn(),
      makeRef(false) as never,
      makeRef([]) as never,
      "/assets/audio-worklet-processor-abc123.js",
      makeRef(null) as never,
      jest.fn(),
    );

    expect(mediaStreamRef.current).not.toBeNull();
  });
});
