import { useStartRecording } from "../use-start-recording";

const makeRef = <T>(current: T) => ({ current });

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
let originalMediaDevicesDescriptor: PropertyDescriptor | undefined;
let originalCreateObjectURLDescriptor: PropertyDescriptor | undefined;

function restoreProperty(
  target: object,
  key: string,
  descriptor: PropertyDescriptor | undefined,
) {
  if (descriptor) {
    Object.defineProperty(target, key, descriptor);
  } else {
    Reflect.deleteProperty(target, key);
  }
}

beforeEach(() => {
  originalMediaDevicesDescriptor = Object.getOwnPropertyDescriptor(
    navigator,
    "mediaDevices",
  );
  originalCreateObjectURLDescriptor = Object.getOwnPropertyDescriptor(
    URL,
    "createObjectURL",
  );
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    writable: true,
    value: jest.fn(() => "blob:unexpected-worklet"),
  });
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
  restoreProperty(
    globalThis,
    "AudioWorkletNode",
    originalAudioWorkletNodeDescriptor,
  );
  restoreProperty(navigator, "mediaDevices", originalMediaDevicesDescriptor);
  restoreProperty(URL, "createObjectURL", originalCreateObjectURLDescriptor);
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
  it("loads the packaged URL, retains the stream, and starts recording without a Blob", async () => {
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
    expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(refs.mediaStreamRef.current).toBe(stream);
    expect(setIsRecording).toHaveBeenCalledWith(true);
  });

  it("reports a packaged worklet loading failure through setStatus", async () => {
    const addModule = jest
      .fn()
      .mockRejectedValue(new Error("asset unavailable"));
    const { refs } = setup({ addModule });
    const setStatus = jest.fn();
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
      setStatus,
    );

    expect(addModule).toHaveBeenCalledWith(
      "/assets/audio-worklet-processor-123.js",
    );
    expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(setIsRecording).not.toHaveBeenCalled();
    expect(setStatus).toHaveBeenCalledWith(
      "Error initializing audio: asset unavailable",
    );
  });
});
