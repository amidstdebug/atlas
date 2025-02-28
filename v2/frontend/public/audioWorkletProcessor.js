class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        // Keep a smaller buffer for less latency but still reasonable size
        this.bufferSize = 44100 * 2; // 2 seconds of audio at 44.1kHz
        this.buffer = new Float32Array(this.bufferSize);
        this.bufferIndex = 0;
        this.sampleRate = 44100; // Ensure we know our sample rate
        this.minBufferToSend = this.bufferSize; // Set minimum buffer size to send
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

            // Only send if buffer is full (matches or exceeds min size)
            if (this.bufferIndex + remainingSpace >= this.minBufferToSend) {
                // Send the full buffer
                this.port.postMessage(
                    {
                        audioData: this.buffer.buffer,
                        sampleRate: this.sampleRate,
                    },
                    [this.buffer.buffer],
                );

                // Create a new buffer
                this.buffer = new Float32Array(this.bufferSize);

                // Copy any remaining samples to the start of the new buffer
                const remaining = channelData.slice(remainingSpace);
                this.buffer.set(remaining);
                this.bufferIndex = remaining.length;
            } else {
                console.log("Buffer not full enough, continuing to collect audio");
            }
        } else {
            // Just append to buffer
            this.buffer.set(channelData, this.bufferIndex);
            this.bufferIndex += channelData.length;

            // Check if we've reached minimum buffer size
            if (this.bufferIndex >= this.minBufferToSend) {
                // Send the filled portion of the buffer
                const filledBuffer = this.buffer.slice(0, this.bufferIndex);
                this.port.postMessage(
                    {
                        audioData: filledBuffer.buffer,
                        sampleRate: this.sampleRate,
                    },
                    [filledBuffer.buffer],
                );

                // Reset buffer
                this.buffer = new Float32Array(this.bufferSize);
                this.bufferIndex = 0;
            }
        }

        return true;
    }
}

registerProcessor("audio-processor", AudioProcessor);
