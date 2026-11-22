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
    analyser,
    source,
  };
}

let originalAudioWorkletNodeDescriptor: PropertyDescriptor | undefined;
let originalMediaDevicesDescriptor: PropertyDescriptor | undefined;
let originalCreateObjectURLDescriptor: PropertyDescriptor | undefined;
let audioWorkletNodeConstructor: jest.Mock;
let audioWorkletNode: { connect: jest.Mock; port: { onmessage: null } };

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
  audioWorkletNode = {
    connect: jest.fn(),
    port: { onmessage: null },
  };
  audioWorkletNodeConstructor = jest.fn(() => audioWorkletNode);
  Object.defineProperty(globalThis, "AudioWorkletNode", {
    configurable: true,
    writable: true,
    value: audioWorkletNodeConstructor,
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

function setup(overrides?: {
  addModule?: jest.Mock;
  getUserMedia?: jest.Mock;
}) {
  const audioContext = createAudioContext();
  if (overrides?.addModule) {
    audioContext.audioWorklet.addModule =
      overrides.addModule as typeof audioContext.audioWorklet.addModule;
  }
  const stream = {
    getTracks: () => [{ stop: jest.fn() }],
  } as unknown as MediaStream;
  const getUserMedia =
    overrides?.getUserMedia ?? jest.fn().mockResolvedValue(stream);
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia },
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
  it("waits for the packaged worklet before wiring and starting recording", async () => {
    let resolveAddModule!: () => void;
    let resolveAddModuleRequest!: () => void;
    const addModuleRequest = new Promise<void>((resolve) => {
      resolveAddModuleRequest = resolve;
    });
    const addModule = jest.fn(() => {
      resolveAddModuleRequest();
      return new Promise<void>((resolve) => {
        resolveAddModule = resolve;
      });
    });
    const { audioContext, stream, refs } = setup({ addModule });
    const setIsRecording = jest.fn();

    const startRecording = useStartRecording(
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

    await addModuleRequest;

    expect(audioContext.audioWorklet.addModule).toHaveBeenCalledWith(
      "/assets/audio-worklet-processor-123.js",
    );
    expect(audioWorkletNodeConstructor).not.toHaveBeenCalled();
    expect(setIsRecording).not.toHaveBeenCalled();

    resolveAddModule();
    await startRecording;

    expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(refs.mediaStreamRef.current).toBe(stream);
    expect(audioWorkletNodeConstructor).toHaveBeenCalledWith(
      audioContext,
      "stream_processor",
    );
    expect(audioContext.source.connect).toHaveBeenCalledWith(
      audioContext.analyser,
    );
    expect(audioContext.analyser.connect).toHaveBeenCalledWith(
      audioWorkletNode,
    );
    expect(audioWorkletNode.connect).toHaveBeenCalledWith(
      audioContext.destination,
    );
    expect(setIsRecording).toHaveBeenCalledWith(true);
  });

  it("reports a packaged worklet loading failure through setStatus", async () => {
    const addModule = jest
      .fn()
      .mockRejectedValue(new Error("asset unavailable"));
    const { audioContext, refs } = setup({ addModule });
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
    expect(audioWorkletNodeConstructor).not.toHaveBeenCalled();
    expect(audioContext.analyser.connect).not.toHaveBeenCalled();
    expect(audioWorkletNode.connect).not.toHaveBeenCalled();
    expect(setIsRecording).not.toHaveBeenCalledWith(true);
    expect(setStatus).toHaveBeenCalledWith(
      "Error initializing audio: asset unavailable",
    );
  });
});
