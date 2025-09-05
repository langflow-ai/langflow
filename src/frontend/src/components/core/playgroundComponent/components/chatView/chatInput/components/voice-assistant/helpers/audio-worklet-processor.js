class StreamProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.bufferSize = 4096;
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
    // Increase threshold for much less sensitivity
    this.noiseThreshold = 0.15;
    // Require more consecutive frames above threshold to trigger speech detection
    this.activationThreshold = 8;
    this.silenceFrameCount = 0;
    this.activationCount = 0;
    this.isSpeaking = false;
    this.port.onmessage = this.handleMessage.bind(this);
  }

  handleMessage(event) {
    if (event.data.type === "updateNoiseGate") {
      this.noiseThreshold = event.data.threshold;
    }
  }

  calculateRMS(buffer) {
    let sum = 0;
    for (let i = 0; i < buffer.length; i++) {
      sum += buffer[i] * buffer[i];
    }
    return Math.sqrt(sum / buffer.length);
  }

  process(inputs, outputs) {
    const input = inputs[0];
    if (!input || !input.length) return true;

    const channel = input[0];

    // Calculate RMS volume
    const rms = this.calculateRMS(channel);

    // Scale the RMS value to match the scale used in use-bar-controls.ts
    // This makes the threshold more comparable to the "3" value
    const scaledRMS = rms * 10;

    // Use scaled value for detection
    const isSilent = scaledRMS < 3;

    // Voice activity detection logic with stricter requirements
    if (isSilent) {
      this.activationCount = 0;
      this.silenceFrameCount++;
      // Require more silent frames before deciding speech has ended
      if (this.silenceFrameCount > 20 && this.isSpeaking) {
        this.isSpeaking = false;
      }
    } else {
      this.silenceFrameCount = 0;
      if (!this.isSpeaking) {
        // Require multiple consecutive frames above threshold to start speech
        this.activationCount++;
        if (this.activationCount >= this.activationThreshold) {
          this.isSpeaking = true;
        }
      }
    }

    // Fill buffer with audio data
    for (let i = 0; i < channel.length; i++) {
      if (this.bufferIndex < this.bufferSize) {
        // Apply noise gate - zero out audio when not speaking
        this.buffer[this.bufferIndex++] = !this.isSpeaking ? 0 : channel[i];
      }
    }

    // When buffer is full, send it to the main thread
    if (this.bufferIndex >= this.bufferSize) {
      const audioData = this.buffer.slice(0);
      this.port.postMessage({
        type: "input",
        audio: audioData,
        isSilent: !this.isSpeaking,
        volume: scaledRMS, // Send scaled volume for consistency
      });
      this.bufferIndex = 0;
    }

    return true;
  }
}

registerProcessor("stream_processor", StreamProcessor);
