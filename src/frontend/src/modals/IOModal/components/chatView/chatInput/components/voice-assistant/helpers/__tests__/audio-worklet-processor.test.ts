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
  const sandbox = {
    AudioWorkletProcessor: class {
      port = { onmessage: null, postMessage: jest.fn() };
    },
    Float32Array,
    Int16Array,
    registerProcessor: jest.fn(
      (_name: string, processor: new () => Processor) => {
        ProcessorClass = processor;
      },
    ),
  };
  const source = readFileSync(
    resolve(__dirname, "../audio-worklet-processor.js"),
    "utf8",
  );
  vm.runInNewContext(source, sandbox);
  return new ProcessorClass!();
}

describe("audio worklet processor", () => {
  it("frames input into 128-sample clipped Int16 packets", () => {
    const processor = createProcessor();
    const firstHalf = new Float32Array(64);
    firstHalf[0] = 1.2;
    firstHalf[1] = -1.2;
    firstHalf[2] = 0.5;
    firstHalf[3] = -0.5;

    processor.process([[firstHalf]], []);
    expect(processor.port.postMessage).not.toHaveBeenCalled();

    processor.process([[new Float32Array(64)]], []);

    expect(processor.port.postMessage).toHaveBeenCalledTimes(1);
    const message = processor.port.postMessage.mock.calls[0][0];
    expect(message.type).toBe("input");
    expect(message.audio).toBeInstanceOf(Int16Array);
    expect(Array.from(message.audio.slice(0, 4))).toEqual([
      32767, -32767, 16383, -16383,
    ]);
  });

  it("plays queued audio at 0.8 gain and reports done after the queue drains", () => {
    const processor = createProcessor();
    processor.port.onmessage?.({
      data: { type: "playback", audio: new Float32Array([0.25, -0.5, 1, -1]) },
    });

    const firstChannel = new Float32Array(2);
    const secondChannel = new Float32Array(2);
    processor.process([], [[firstChannel, secondChannel]]);
    expect(firstChannel[0]).toBeCloseTo(0.2);
    expect(firstChannel[1]).toBeCloseTo(-0.4);
    expect(secondChannel[0]).toBeCloseTo(0.2);
    expect(secondChannel[1]).toBeCloseTo(-0.4);
    expect(processor.port.postMessage).not.toHaveBeenCalled();

    const finalChannel = new Float32Array(2);
    processor.process([], [[finalChannel]]);
    expect(finalChannel[0]).toBeCloseTo(0.8);
    expect(finalChannel[1]).toBeCloseTo(-0.8);
    expect(processor.port.postMessage).toHaveBeenCalledWith({ type: "done" });
  });

  it("clears queued playback immediately and acknowledges stop", () => {
    const processor = createProcessor();
    processor.port.onmessage?.({
      data: { type: "playback", audio: new Float32Array([1, 1]) },
    });
    processor.port.onmessage?.({ data: { type: "stop_playback" } });

    expect(processor.port.postMessage).toHaveBeenCalledWith({ type: "done" });
    processor.port.postMessage.mockClear();
    processor.process([], [[new Float32Array(2)]]);
    expect(processor.port.postMessage).not.toHaveBeenCalled();
  });
});
