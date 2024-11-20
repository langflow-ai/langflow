export const workletCode = `
  class StreamProcessor extends AudioWorkletProcessor {
    constructor() {
      super();
      this.inputBuffer = new Float32Array(128);
      this.inputOffset = 0;
      this.outputBuffers = [];
      this.isPlaying = false;

      this.port.onmessage = (event) => {
        if (event.data.type === 'playback') {
          this.outputBuffers.push(event.data.audio);
          this.isPlaying = true;
        }
      };
    }

    process(inputs, outputs, parameters) {
      const input = inputs[0];
      if (input && input.length > 0) {
        const inputData = input[0];
        for (let i = 0; i < inputData.length; i++) {
          this.inputBuffer[this.inputOffset++] = inputData[i];

          if (this.inputOffset >= this.inputBuffer.length) {
            const outputData = new Int16Array(this.inputBuffer.length);
            for (let j = 0; j < this.inputBuffer.length; j++) {
              outputData[j] = Math.max(-1, Math.min(1, this.inputBuffer[j])) * 0x7FFF;
            }
            this.port.postMessage({
              type: 'input',
              audio: outputData
            });
            this.inputBuffer = new Float32Array(128);
            this.inputOffset = 0;
          }
        }
      }

      const output = outputs[0];
      if (output && output.length > 0 && this.isPlaying) {
        if (this.outputBuffers.length > 0) {
          const currentBuffer = this.outputBuffers[0];
          const chunkSize = Math.min(output[0].length, currentBuffer.length);

          const gain = 0.8;
          for (let channel = 0; channel < output.length; channel++) {
            const outputChannel = output[channel];
            for (let i = 0; i < chunkSize; i++) {
              outputChannel[i] = currentBuffer[i] * gain;
            }
          }

          if (chunkSize === currentBuffer.length) {
            this.outputBuffers.shift();
          } else {
            this.outputBuffers[0] = currentBuffer.slice(chunkSize);
          }
        }

        if (this.outputBuffers.length === 0) {
          this.isPlaying = false;
          this.port.postMessage({ type: 'done' });
        }
      }
      return true;
    }
  }
  registerProcessor('stream_processor', StreamProcessor);
`;
