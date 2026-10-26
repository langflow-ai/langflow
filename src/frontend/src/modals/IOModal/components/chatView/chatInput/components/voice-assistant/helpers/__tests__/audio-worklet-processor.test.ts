import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import vm from "node:vm";

type Processor = {
  port: {
    onmessage:
      | ((event: { data: { type: string; audio?: Float32Array } }) => void)
      | null;
    postMessage: jest.Mock;
  };
  process: (inputs: Float32Array[][], outputs: Float32Array[][]) => boolean;
};

function createProcessor() {
  let ProcessorClass: new () => Processor;
  let registeredProcessorName: string | undefined;
  const sandbox = {
    AudioWorkletProcessor: class {
      port = { onmessage: null, postMessage: jest.fn() };
    },
    Float32Array,
    Int16Array,
    registerProcessor: jest.fn(
      (name: string, processor: new () => Processor) => {
        registeredProcessorName = name;
        ProcessorClass = processor;
      },
    ),
  };
  const source = readFileSync(
    resolve(__dirname, "../audio-worklet-processor.js"),
    "utf8",
  );
  vm.runInNewContext(source, sandbox);
  return {
    processor: new ProcessorClass!(),
    registeredProcessorName,
  };
}

describe("audio worklet processor", () => {
  it("frames input into 128-sample clipped Int16 packets", () => {
    const { processor, registeredProcessorName } = createProcessor();
    const firstHalf = new Float32Array(64);
    firstHalf[0] = 1.2;
    firstHalf[1] = -1.2;
    firstHalf[2] = 0.5;
    firstHalf[3] = -0.5;
    const secondHalf = new Float32Array(128);
    secondHalf[64] = 0.25;
    const rolloverHalf = new Float32Array(64);
    rolloverHalf[0] = -0.75;

    expect(registeredProcessorName).toBe("stream_processor");
    processor.process([[firstHalf]], []);
    expect(processor.port.postMessage).not.toHaveBeenCalled();

    processor.process([[secondHalf]], []);

    expect(processor.port.postMessage).toHaveBeenCalledTimes(1);
    const firstMessage = processor.port.postMessage.mock.calls[0][0];
    expect(firstMessage.type).toBe("input");
    expect(firstMessage.audio).toBeInstanceOf(Int16Array);
    expect(firstMessage.audio).toHaveLength(128);
    expect(Array.from(firstMessage.audio.slice(0, 4))).toEqual([
      32767, -32767, 16383, -16383,
    ]);

    processor.process([[rolloverHalf]], []);

    expect(processor.port.postMessage).toHaveBeenCalledTimes(2);
    const secondMessage = processor.port.postMessage.mock.calls[1][0];
    expect(secondMessage.audio).toHaveLength(128);
    expect(Array.from(secondMessage.audio.slice(0, 2))).toEqual([8191, 0]);
    expect(secondMessage.audio[64]).toBe(-24575);
  });

  it("plays queued audio at 0.8 gain and reports done after the queue drains", () => {
    const { processor } = createProcessor();
    processor.port.onmessage?.({
      data: { type: "playback", audio: new Float32Array([0.25, -0.5, 1, -1]) },
    });
    processor.port.onmessage?.({
      data: { type: "playback", audio: new Float32Array([0.5, -0.25]) },
    });

    const firstChannel = new Float32Array(2);
    const secondChannel = new Float32Array(2);
    processor.process([], [[firstChannel, secondChannel]]);
    expect(firstChannel[0]).toBeCloseTo(0.2);
    expect(firstChannel[1]).toBeCloseTo(-0.4);
    expect(secondChannel[0]).toBeCloseTo(0.2);
    expect(secondChannel[1]).toBeCloseTo(-0.4);
    expect(processor.port.postMessage).not.toHaveBeenCalled();

    const secondBufferChannel = new Float32Array(2);
    processor.process([], [[secondBufferChannel]]);
    expect(secondBufferChannel[0]).toBeCloseTo(0.8);
    expect(secondBufferChannel[1]).toBeCloseTo(-0.8);
    expect(processor.port.postMessage).not.toHaveBeenCalled();

    const finalChannel = new Float32Array(2);
    processor.process([], [[finalChannel]]);
    expect(finalChannel[0]).toBeCloseTo(0.4);
    expect(finalChannel[1]).toBeCloseTo(-0.2);
    expect(processor.port.postMessage).toHaveBeenCalledWith({ type: "done" });

    processor.process([], [[new Float32Array(2)]]);
    expect(processor.port.postMessage).toHaveBeenCalledTimes(1);
  });

  it("clears queued playback immediately and acknowledges stop", () => {
    const { processor } = createProcessor();
    processor.port.onmessage?.({
      data: { type: "playback", audio: new Float32Array([1, 1]) },
    });
    processor.port.onmessage?.({ data: { type: "stop_playback" } });

    expect(processor.port.postMessage).toHaveBeenCalledWith({ type: "done" });
    processor.port.postMessage.mockClear();
    const stoppedChannel = new Float32Array(2);
    processor.process([], [[stoppedChannel]]);
    expect(Array.from(stoppedChannel)).toEqual([0, 0]);
    expect(processor.port.postMessage).not.toHaveBeenCalled();

    processor.port.onmessage?.({
      data: { type: "playback", audio: new Float32Array([0.5, -0.25]) },
    });
    const restartedChannel = new Float32Array(2);
    processor.process([], [[restartedChannel]]);
    expect(restartedChannel[0]).toBeCloseTo(0.4);
    expect(restartedChannel[1]).toBeCloseTo(-0.2);
    expect(processor.port.postMessage).toHaveBeenCalledWith({ type: "done" });
  });
});
