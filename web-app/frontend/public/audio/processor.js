// public/audio/processor.js

class RecorderProcessor extends AudioWorkletProcessor {
  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (input && input[0]) {
      // Send the input audio samples to the main thread
      this.port.postMessage(input[0]);
    }
    return true; // Keep processor alive
  }
}

registerProcessor('recorder-processor', RecorderProcessor);
