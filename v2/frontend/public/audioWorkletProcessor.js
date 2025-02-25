class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    // Keep a smaller buffer for less latency
    this.bufferSize = 44100 * 2; 
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
    this.sampleRate = 44100; // Ensure we know our sample rate
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channelData = input[0];

    // Instead of sample-by-sample copying, use set() to copy chunks
    if (this.bufferIndex + channelData.length > this.bufferSize) {
      // Fill what we can
      const remainingSpace = this.bufferSize - this.bufferIndex;
      if (remainingSpace > 0) {
        this.buffer.set(channelData.slice(0, remainingSpace), this.bufferIndex);
      }
      
      // Send the full buffer
      this.port.postMessage({
        audioData: this.buffer.buffer,
        sampleRate: this.sampleRate
      }, [this.buffer.buffer]);
      
      // Create a new buffer
      this.buffer = new Float32Array(this.bufferSize);
      
      // Copy any remaining samples to the start of the new buffer
      const remaining = channelData.slice(remainingSpace);
      this.buffer.set(remaining);
      this.bufferIndex = remaining.length;
    } else {
      // Just append to buffer
      this.buffer.set(channelData, this.bufferIndex);
      this.bufferIndex += channelData.length;
    }

    return true;
  }
}

registerProcessor("audio-processor", AudioProcessor);