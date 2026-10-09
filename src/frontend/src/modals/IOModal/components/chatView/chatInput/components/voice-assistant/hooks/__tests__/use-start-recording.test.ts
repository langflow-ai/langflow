import { useStartRecording } from "../use-start-recording";

const makeRef = <T>(current: T) => ({ current }) as { current: T };

function createAudioContext() {
  const analyser = { fftSize: 0, connect: jest.fn() };
  const source = { connect: jest.fn() };
  return {
    audioWorklet: { addModule: jest.fn().mockResolvedValue(undefined) },
    createMediaStreamSource: jest.fn(() => source),
    createAnalyser: jest.fn(() => analyser),
    destination: {},
  };
}

let originalAudioWorkletNodeDescriptor: PropertyDescriptor | undefined;

beforeEach(() => {
  originalAudioWorkletNodeDescriptor = Object.getOwnPropertyDescriptor(
    globalThis,
    "AudioWorkletNode",
  );
  Object.defineProperty(globalThis, "AudioWorkletNode", {
    configurable: true,
    writable: true,
    value: jest.fn(() => ({
      connect: jest.fn(),
      port: { onmessage: null },
    })),
  });
});

afterEach(() => {
  if (originalAudioWorkletNodeDescriptor) {
    Object.defineProperty(
      globalThis,
      "AudioWorkletNode",
      originalAudioWorkletNodeDescriptor,
    );
  } else {
    Reflect.deleteProperty(globalThis, "AudioWorkletNode");
  }
});

function setup(overrides?: { addModule?: jest.Mock }) {
  const audioContext = createAudioContext();
  if (overrides?.addModule) {
    audioContext.audioWorklet.addModule =
      overrides.addModule as typeof audioContext.audioWorklet.addModule;
  }
  const stream = {
    getTracks: () => [{ stop: jest.fn() }],
  } as unknown as MediaStream;
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: jest.fn().mockResolvedValue(stream) },
  });
  const refs = {
    audioContextRef: makeRef(audioContext as unknown as AudioContext),
    microphoneRef: makeRef<MediaStreamAudioSourceNode | null>(null),
    analyserRef: makeRef<AnalyserNode | null>(null),
    wsRef: makeRef<WebSocket | null>(null),
    mediaStreamRef: makeRef<MediaStream | null>(null),
    processorRef: makeRef<AudioWorkletNode | null>(null),
  };
  return { audioContext, stream, refs };
}

describe("useStartRecording", () => {
  it("loads the packaged URL and starts recording", async () => {
    const { audioContext, stream, refs } = setup();
    const setIsRecording = jest.fn();

    await useStartRecording(
      refs.audioContextRef,
      refs.microphoneRef,
      refs.analyserRef,
      refs.wsRef,
      refs.mediaStreamRef,
      setIsRecording,
      jest.fn(),
      makeRef(false),
      makeRef([]),
      "/assets/audio-worklet-processor-123.js",
      refs.processorRef,
      jest.fn(),
    );

    expect(audioContext.audioWorklet.addModule).toHaveBeenCalledWith(
      "/assets/audio-worklet-processor-123.js",
    );
    expect(refs.mediaStreamRef.current).toBe(stream);
    expect(setIsRecording).toHaveBeenCalledWith(true);
  });

  it("reports a packaged worklet loading failure through setStatus", async () => {
    const addModule = jest
      .fn()
      .mockRejectedValue(new Error("asset unavailable"));
    const { refs } = setup({ addModule });
    const setStatus = jest.fn();

    await useStartRecording(
      refs.audioContextRef,
      refs.microphoneRef,
      refs.analyserRef,
      refs.wsRef,
      refs.mediaStreamRef,
      jest.fn(),
      jest.fn(),
      makeRef(false),
      makeRef([]),
      "/assets/audio-worklet-processor-123.js",
      refs.processorRef,
      setStatus,
    );

    expect(addModule).toHaveBeenCalledWith(
      "/assets/audio-worklet-processor-123.js",
    );
    expect(setStatus).toHaveBeenCalledWith(
      "Error initializing audio: asset unavailable",
    );
  });
});
