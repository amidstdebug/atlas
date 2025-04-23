export class AudioRecorderService {
  constructor() {
    // Recording settings
    this.sampleRate = 48000;
    this.maxRecordingDuration = 5; // seconds per chunk
    this.recordedSamples = [];
    this.isRecording = false;
    this.intervalId = null;

    // Audio context and stream
    this.audioContext = null;
    this.audioStream = null;
    this.audioWorkletNode = null;
  }

  async setupAudio() {
    try {
      console.log("Requesting microphone access...");
      this.audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      if (this.audioContext.state === "suspended") {
        await this.audioContext.resume();
      }
      this.sampleRate = this.audioContext.sampleRate;

      const source = this.audioContext.createMediaStreamSource(this.audioStream);

      // Load the audio processor worklet (make sure processor.js is served at this path)
      const processorPath = "/atlas/audio/processor.js";
      console.log("Loading audio processor from:", processorPath);
      await this.audioContext.audioWorklet.addModule(processorPath);
      this.audioWorkletNode = new AudioWorkletNode(this.audioContext, "recorder-processor");

      // Connect source to worklet
      source.connect(this.audioWorkletNode);

      // Connect to a dummy gain node to keep the processing active
      const dummyGain = this.audioContext.createGain();
      dummyGain.gain.value = 0;
      this.audioWorkletNode.connect(dummyGain);
      dummyGain.connect(this.audioContext.destination);

      // Collect audio samples sent from the processor
      this.audioWorkletNode.port.onmessage = (event) => {
        const audioData = event.data;
        if (this.isRecording && audioData?.length) {
          this.recordedSamples.push(...audioData);
        }
      };

      console.log("Audio setup complete.");
    } catch (error) {
      console.error("Error setting up audio:", error);
    }
  }

  async startRecording() {
    if (!this.audioContext) {
      await this.setupAudio();
    }
    this.isRecording = true;
    console.log("Recording started...");

    // Every 5 seconds, save the recorded samples as a WAV file
    this.intervalId = setInterval(() => {
      if (this.recordedSamples.length > 0) {
        this.saveAudio();
        // Clear buffer for next 5-second chunk
        this.recordedSamples = [];
      }
    }, this.maxRecordingDuration * 1000);
  }

  stopRecording() {
    console.log("Stopping recording...");
    this.isRecording = false;
    clearInterval(this.intervalId);
    // Save any remaining samples
    if (this.recordedSamples.length > 0) {
      this.saveAudio();
      this.recordedSamples = [];
    }
    this.closeAudio();
  }

  closeAudio() {
    if (this.audioStream) {
      this.audioStream.getTracks().forEach(track => track.stop());
      this.audioStream = null;
    }
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    console.log("Audio context closed.");
  }

  saveAudio() {
    // Convert the recorded samples to a Float32Array
    const float32Array = new Float32Array(this.recordedSamples);
    // Encode samples as WAV
    const wavBlob = this.encodeWAV(float32Array, this.sampleRate);
    // Create a unique filename using timestamp
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const filename = `recorded-${timestamp}.wav`;
    this.downloadWAV(wavBlob, filename);
    console.log(`Saved ${filename}`);
  }

  // ----- WAV ENCODING HELPERS -----

  encodeWAV(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    // RIFF header
    this.writeString(view, 0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    this.writeString(view, 8, "WAVE");

    // fmt chunk
    this.writeString(view, 12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM format
    view.setUint16(22, 1, true); // Mono channel
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); // Byte rate
    view.setUint16(32, 2, true); // Block align
    view.setUint16(34, 16, true); // Bits per sample

    // data chunk
    this.writeString(view, 36, "data");
    view.setUint32(40, samples.length * 2, true);

    this.floatTo16BitPCM(view, 44, samples);
    return new Blob([view], { type: "audio/wav" });
  }

  writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  floatTo16BitPCM(view, offset, input) {
    const gain = 1.2; // Slight gain boost
    for (let i = 0; i < input.length; i++, offset += 2) {
      let s = Math.max(-1, Math.min(1, input[i] * gain));
      s = s < 0 ? s * 0x8000 : s * 0x7fff;
      view.setInt16(offset, s, true);
    }
  }

  downloadWAV(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.style.display = "none";
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 100);
  }
}
