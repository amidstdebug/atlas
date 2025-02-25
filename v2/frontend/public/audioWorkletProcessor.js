class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 80000; 
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channelData = input[0];

    // Add data to buffer
    for (let i = 0; i < channelData.length; i++) {
      if (this.bufferIndex >= this.bufferSize) {
        // Buffer is full, send it using transferable objects
        this.port.postMessage({
          audioData: this.buffer.buffer
        }, [this.buffer.buffer]);
        
        // Create a new buffer after the transfer
        this.buffer = new Float32Array(this.bufferSize);
        this.bufferIndex = 0;
      }
      this.buffer[this.bufferIndex++] = channelData[i];
    }

    return true;
  }
}

registerProcessor("audio-processor", AudioProcessor);