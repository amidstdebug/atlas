// processor.js
class RecorderProcessor extends AudioWorkletProcessor {
  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (input && input[0]) {
      // Send the input audio samples to the main thread
      const samples = input[0];

      // Clone the samples to avoid issues with transferring
      const clonedSamples = new Float32Array(samples.length);
      clonedSamples.set(samples);

      this.port.postMessage(clonedSamples);
    }
    return true; // Keep processor alive
  }
}

registerProcessor('recorder-processor', RecorderProcessor);
