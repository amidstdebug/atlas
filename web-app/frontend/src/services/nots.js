// AudioRecorderService.js

export class AudioRecorderService {
  constructor(options = {}) {
    // Server URL
    this.apiUrl = options.apiUrl || "http://localhost:5002";
    
    // Recording & interval settings
    this.sampleRate = 48000;
    this.maxRecordingDuration = 5; // seconds; we send in 5s chunks
    this.transcriptionInterval = null;
    this.recordedSamples = [];
    this.isRecording = false;
    this.isSending = false;

    // Local save settings
    this.saveAudioLocally = options.saveAudioLocally ?? false;
    this.lastSavedAudioTimestamp = 0;
    this.minTimeBetweenSaves = 5000; // default 30 seconds between forced local saves

    // External callbacks
    this.onTranscription = null; // (text) => ...
    this.onStatusChange = null;  // (statusObj) => ...

    // Audio context references
    this.audioContext = null;
    this.audioStream = null;
    this.audioWorkletNode = null;

    console.log(`AudioRecorderService initialized. Local save: ${this.saveAudioLocally}`);
  }

  // --------------------------------------------------------------------------
  // 1) SETUP AUDIO
  // --------------------------------------------------------------------------
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

        // Load the audio processor worklet
        const processorPath = "/atlas/audio/processor.js";
        console.log("Loading audio processor from:", processorPath);
        
        await this.audioContext.audioWorklet
        .addModule(processorPath)
        .catch((error) => {
            console.error("Error loading AudioWorkletProcessor:", error);
            this.updateStatus({ error: true, lastErrorMessage: "Failed to load audio processor" });
        });

        // Create the AudioWorkletNode
        this.audioWorkletNode = new AudioWorkletNode(this.audioContext, "recorder-processor");
        source.connect(this.audioWorkletNode);

        // **Fix: Connect the worklet node to a dummy gain node so processing is not optimized away**
        const dummyGain = this.audioContext.createGain();
        dummyGain.gain.value = 0;
        this.audioWorkletNode.connect(dummyGain);
        dummyGain.connect(this.audioContext.destination);

        // Listen for audio data from the worklet
        this.audioWorkletNode.port.onmessage = (event) => {
        const audioData = event.data;
        if (this.isRecording && audioData?.length) {
            this.recordedSamples.push(...audioData);
        }
        };

        console.log("Microphone setup complete.");
    } catch (error) {
        console.error("Error in setupAudio:", error);
        this.updateStatus({ error: true, lastErrorMessage: "Failed to access microphone" });
    }
    }


  // --------------------------------------------------------------------------
  // 2) START / STOP RECORDING
  // --------------------------------------------------------------------------
  async startRecording() {
    if (!this.audioContext) {
      await this.setupAudio();
    } else if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }

    this.isRecording = true;
    console.log("Recording started...");

    // Send audio every 5 seconds
    const chunkInterval = this.maxRecordingDuration * 1000; // 5000ms
    this.transcriptionInterval = setInterval(() => {
      if (this.recordedSamples.length > 0) {
        console.log(`Sending ${this.recordedSamples.length} samples (5s chunk)`);
        this.sendRecordedAudio();
      }
    }, chunkInterval);
  }

  async stopRecording() {
    console.log("Stopping recording...");
    this.isRecording = false;

    if (this.transcriptionInterval) {
      clearInterval(this.transcriptionInterval);
      this.transcriptionInterval = null;
    }

    // Send any leftover samples
    if (this.recordedSamples.length > 0) {
      await this.sendRecordedAudio();
    }

    this.closeAudio();
    this.resetState();
  }

  // --------------------------------------------------------------------------
  // 3) TEARDOWN & RESET
  // --------------------------------------------------------------------------
  closeAudio() {
    if (this.audioStream) {
      this.audioStream.getTracks().forEach((track) => track.stop());
      this.audioStream = null;
    }
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    console.log("Audio context closed.");
  }

  resetState() {
    this.recordedSamples = [];
    this.isRecording = false;
    this.isSending = false;
    console.log("State reset.");
  }

  // --------------------------------------------------------------------------
  // 4) ENCODE & SEND AUDIO (WAV)
  // --------------------------------------------------------------------------
  async sendRecordedAudio() {
    if (this.isSending) {
      console.log("Already sending audio, skipping.");
      return;
    }
    if (!this.recordedSamples.length) {
      console.warn("No audio samples to send.");
      return;
    }

    this.isSending = true;

    try {
      // Copy the current samples
      let float32Array = new Float32Array(this.recordedSamples);
      // Clear out the original buffer
      this.recordedSamples = [];

      // Keep only the last 5 seconds to avoid huge arrays
      const maxSamples = 5 * this.sampleRate;
      if (float32Array.length > maxSamples) {
        float32Array = float32Array.slice(-maxSamples);
      }

      console.log(
        `Preparing ${float32Array.length} samples at ${this.sampleRate} Hz for sending.`
      );

      // Downsample to 16k using a better algorithm (averaging)
      const desiredRate = 16000;
      if (this.sampleRate > desiredRate) {
        const ratio = this.sampleRate / desiredRate;
        const downsampledLength = Math.floor(float32Array.length / ratio);
        const downsampledData = new Float32Array(downsampledLength);
        
        for (let i = 0; i < downsampledLength; i++) {
          // Use averaging to improve sound quality during downsampling
          const startIndex = Math.floor(i * ratio);
          const endIndex = Math.min(Math.floor((i + 1) * ratio), float32Array.length);
          let sum = 0;
          let count = 0;
          
          for (let j = startIndex; j < endIndex; j++) {
            sum += float32Array[j];
            count++;
          }
          
          downsampledData[i] = count > 0 ? sum / count : 0;
        }
        
        float32Array = downsampledData;
        console.log(`Downsampled to ${desiredRate} Hz: ${float32Array.length} samples total.`);
      }

      // Encode as WAV
      const wavBlob = encodeWAV(float32Array, desiredRate);

      // Optionally save locally
      const now = Date.now();
      const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
      if (
        this.saveAudioLocally &&
        now - this.lastSavedAudioTimestamp > this.minTimeBetweenSaves
      ) {
        downloadWAV(wavBlob, `recorded-${timestamp}.wav`);
        this.lastSavedAudioTimestamp = now;
        console.log(`Saved .wav locally as recorded-${timestamp}.wav`);
      }

      // Prepare POST
      const formData = new FormData();
      formData.append("file", wavBlob, `recording-${timestamp}.wav`);

      const token = this.getCookie("auth_token");

      // POST to server
      console.log("Posting audio data...");
      const response = await fetch(`${this.apiUrl}/transcribe`, {
        method: "POST",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: formData,
        credentials: "include"
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error("Server error:", errorText);
        this.updateStatus({ error: true, lastErrorMessage: errorText });
      } else {
        const result = await response.json();
        const transcription = result.transcription || "";
        console.log("Transcription:", transcription);
        if (this.onTranscription) {
          this.onTranscription(transcription);
        }
      }
    } catch (err) {
      console.error("Error sending audio:", err);
      this.updateStatus({ error: true, lastErrorMessage: err.message });
    } finally {
      this.isSending = false;
    }
  }

  // --------------------------------------------------------------------------
  // 5) HELPERS
  // --------------------------------------------------------------------------
  setSaveAudioLocally(enable, minInterval = 30000) {
    this.saveAudioLocally = !!enable;
    this.minTimeBetweenSaves = minInterval;
    this.lastSavedAudioTimestamp = 0; // reset so next save can happen
    console.log(
      `Local audio saving ${this.saveAudioLocally ? "enabled" : "disabled"},` +
        ` min interval: ${this.minTimeBetweenSaves}ms`
    );
    return this.saveAudioLocally;
  }

  updateStatus(statusObj) {
    // Simple status callback
    if (this.onStatusChange) {
      this.onStatusChange(statusObj);
    }
  }

  getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
  }
}

// --------------------------------------------------------------------------------
// WAV ENCODING HELPERS
// --------------------------------------------------------------------------------

function encodeWAV(samples, sampleRate) {
  // 16-bit PCM
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  /* RIFF header */
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, "WAVE");
  /* fmt chunk */
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM format (1)
  view.setUint16(22, 1, true); // Mono channel (1)
  view.setUint32(24, sampleRate, true); // Sample rate
  view.setUint32(28, sampleRate * 2, true); // Byte rate (SampleRate * NumChannels * BitsPerSample/8)
  view.setUint16(32, 2, true); // Block align (NumChannels * BitsPerSample/8)
  view.setUint16(34, 16, true); // Bits per sample
  /* data chunk */
  writeString(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);

  floatTo16BitPCM(view, 44, samples);

  return new Blob([view], { type: "audio/wav" });
}

function writeString(view, offset, string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}

function floatTo16BitPCM(output, offset, input) {
  // Add a small amount of gain to ensure audio is not too quiet
  const gain = 1.2; // Increase volume slightly
  
  for (let i = 0; i < input.length; i++, offset += 2) {
    // Apply gain and ensure we don't clip
    let s = Math.max(-1, Math.min(1, input[i] * gain));
    
    // Convert to 16-bit PCM
    s = s < 0 ? s * 0x8000 : s * 0x7fff;
    output.setInt16(offset, s, true);
  }
}

function downloadWAV(wavBlob, filename = "recorded-audio.wav") {
  const url = URL.createObjectURL(wavBlob);
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
