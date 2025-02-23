// src/services/audioRecorderService.js

import { encodeWAV } from '@/methods/utils/audioUtils';

export class AudioRecorderService {
  constructor(options = {}) {
    // Recording settings
    this.sampleRate = 48000;
    this.preBufferDuration = options.preBufferDuration || 0.4; // seconds to retain before recording starts
    this.preBufferSize = null;
    this.preBuffer = null;
    this.preBufferIndex = 0;
    this.recordedSamples = [];
    this.isRecording = false;
    this.isSending = false;
    this.chunkNumber = 1;
    this.ws = null; // WebSocket connection

    // Reactivation/chunk–sending settings
    this.thresholdPercentage = 0.1;
    this.sensitivity = { activity: 0.5, reduced: 0.5 };
    this.delayDuration = 250; // ms
    this.forceSendDuration = 8000; // ms
    this.fps = 60;
    this.inactiveTimer = null;
    this.delayTimer = null;
    this.forceSendTimer = null;
    this.reactivationCount = 0;
    this.maxReactivations = 1;
    this.chunkBeepDuration = 250; // ms
    this.conditionCounter = 0;
    this.isActive = false;
    this.chunkSent = false;

    // For reactivation detection using the analyser
    this.analyser = null;
    this.bufferLength = null;
    this.dataArray = null;

    // Audio context and worklet
    this.audioContext = null;
    this.audioStream = null;
    this.audioWorkletNode = null;
  }

  // Sets up the audio input and analysis (no canvas drawing)
  async setupAudio() {
    try {
      // Request microphone access
      this.audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }
      this.sampleRate = this.audioContext.sampleRate;
      const source = this.audioContext.createMediaStreamSource(this.audioStream);

      // Create an analyser node (to measure audio levels for reactivation)
      this.analyser = this.audioContext.createAnalyser();
      source.connect(this.analyser);
      this.bufferLength = this.analyser.frequencyBinCount;
      this.dataArray = new Uint8Array(this.bufferLength);

      // Load audio worklet for recording
      await this.audioContext.audioWorklet.addModule('/atlas/audio/processor.js')
        .catch((error) => {
          console.error('Error loading AudioWorkletProcessor:', error);
        });
      this.audioWorkletNode = new AudioWorkletNode(this.audioContext, 'recorder-processor');
      source.connect(this.audioWorkletNode);

      // Initialize pre–buffer (to keep a short period of audio before recording)
      this.preBufferSize = Math.floor(this.preBufferDuration * this.sampleRate);
      this.preBuffer = new Float32Array(this.preBufferSize);
      this.preBufferIndex = 0;

      // When audio worklet sends data, save it in the pre–buffer and (if recording) into recordedSamples
      this.audioWorkletNode.port.onmessage = (event) => {
        const audioData = event.data;
        if (audioData.length > 0) {
          this.storeInPreBuffer(audioData);
          if (this.isRecording) {
            this.recordedSamples.push(...audioData);
          }
        }
      };
    } catch (error) {
      console.error('Error in setupAudio:', error);
    }
  }

  // Append new samples into the pre–buffer (shifting if needed)
  storeInPreBuffer(audioData) {
    const dataLength = audioData.length;
    if (dataLength + this.preBufferIndex > this.preBufferSize) {
      const overflow = dataLength + this.preBufferIndex - this.preBufferSize;
      this.preBuffer.copyWithin(0, overflow, this.preBufferIndex);
      this.preBufferIndex -= overflow;
    }
    this.preBuffer.set(audioData, this.preBufferIndex);
    this.preBufferIndex += dataLength;
  }

  // Start recording: set up audio if needed, mark recording active,
  // append pre–buffer to recordedSamples, and start reactivation loop.
  async startRecording() {
    if (!this.audioContext) {
      await this.setupAudio();
    } else if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }
    this.isRecording = true;
    // Append pre–buffered audio
    const preBufferData = this.preBuffer.slice(0, this.preBufferIndex);
    this.recordedSamples.push(...preBufferData);
    // Reset pre–buffer index so new data is appended
    this.preBufferIndex = this.preBufferSize;
    // Reset reactivation counter and start loop
    this.conditionCounter = 0;
    this.startReactivationLoop();
  }

  // Stop recording manually: stop reactivation loop, send any pending chunk,
  // close microphone, and reset state.
  async stopRecording() {
    this.isRecording = false;
    // Clear any pending timers in the reactivation logic
    if (this.inactiveTimer) { clearTimeout(this.inactiveTimer); this.inactiveTimer = null; }
    if (this.delayTimer) { clearTimeout(this.delayTimer); this.delayTimer = null; }
    if (this.forceSendTimer) { clearTimeout(this.forceSendTimer); this.forceSendTimer = null; }
    // Send any remaining audio chunk
    await this.sendRecordedAudio();
    // Close microphone and audio context so the mic is no longer in use
    this.closeAudio();
    this.resetState();
  }

  // Closes the audio stream and AudioContext
  closeAudio() {
    if (this.audioStream) {
      this.audioStream.getTracks().forEach(track => track.stop());
      this.audioStream = null;
    }
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }

  resetState() {
    this.recordedSamples = [];
    if (this.preBuffer) {
      this.preBuffer.fill(0);
      this.preBufferIndex = 0;
    }
    this.isRecording = false;
    this.chunkNumber = 1;
    this.conditionCounter = 0;
    this.isActive = false;
    this.chunkSent = false;
    this.reactivationCount = 0;
  }

  // Connect to a WebSocket server for sending chunks
  connectWebSocket(url) {
    this.ws = new WebSocket(url);
    this.ws.onopen = () => { console.log('WebSocket connection established.'); };
    this.ws.onerror = (error) => { console.error('WebSocket error:', error); };
    this.ws.onclose = () => { console.log('WebSocket connection closed.'); };
  }

  // Reactivation loop: repeatedly get analyser data and check if audio level is low.
  startReactivationLoop() {
    const loop = () => {
      if (this.isRecording) {
        // Get time–domain data from the analyser
        this.analyser.getByteTimeDomainData(this.dataArray);
        this.checkThresholdCondition();
        requestAnimationFrame(loop);
      }
    };
    loop();
  }

  // Check if the audio level is below threshold.
  // Here we assume the neutral value is 128 (for an 8–bit time domain array).
  checkThresholdCondition() {
    const center = 128;
    const centerThreshold = center * this.thresholdPercentage;
    const reducedThreshold = centerThreshold * this.sensitivity.reduced;
    const minVal = Math.min(...this.dataArray);
    const maxVal = Math.max(...this.dataArray);
    const withinThreshold = (Math.abs(maxVal - center) < reducedThreshold &&
                             Math.abs(minVal - center) < reducedThreshold);
    if (withinThreshold) {
      this.conditionCounter++;
      const activationThreshold = this.sensitivity.activity * this.fps;
      if (this.conditionCounter >= activationThreshold && this.isActive) {
        if (this.reactivationCount >= this.maxReactivations) {
          this.forceSendChunk('max');
        } else {
          this.deactivateRecording();
        }
      }
    } else {
      if (!this.isActive && !this.chunkSent) {
        this.activateRecording();
      }
      this.conditionCounter = 0;
      if (this.inactiveTimer) {
        clearTimeout(this.inactiveTimer);
        this.inactiveTimer = null;
      }
    }
  }

  // Called when a loud signal is detected, marking the chunk as active.
  activateRecording() {
    console.log('Activating recording (chunk start)');
    this.isActive = true;
    // Record the start time if needed
    this.recordingStartTime = Date.now();
    if (this.delayTimer) { clearTimeout(this.delayTimer); this.delayTimer = null; }
    // Append any remaining pre–buffer data
    const preBufferData = this.preBuffer.slice(0, this.preBufferIndex);
    this.recordedSamples.push(...preBufferData);
    this.preBufferIndex = this.preBufferSize;
    // Set a timer to force–send a chunk if recording goes too long
    this.forceSendTimer = setTimeout(() => { this.forceSendChunk('time'); }, this.forceSendDuration);
    this.conditionCounter = 0;
    this.chunkSent = false;
  }

  // Called when a silent period is detected.
  deactivateRecording() {
    console.log('Deactivating recording (chunk end)');
    this.isActive = false;
    this.delayTimer = setTimeout(() => { this.startInactiveTimer(); }, this.delayDuration);
    this.reactivationCount++;
    this.chunkSent = false;
  }

  // When silence persists, force–send the current chunk.
  forceSendChunk(reason) {
    console.log(`Force–sending chunk due to ${reason}`);
    this.sendRecordedAudio();
    if (this.forceSendTimer) { clearTimeout(this.forceSendTimer); this.forceSendTimer = null; }
    this.chunkSent = true;
    setTimeout(() => { this.chunkSent = false; }, this.chunkBeepDuration);
    this.isActive = false;
  }

  // If silence continues, start an inactive timer that sends the chunk.
  startInactiveTimer() {
    if (this.inactiveTimer) return;
    this.inactiveTimer = setTimeout(() => {
      this.sendRecordedAudio();
      this.reactivationCount = 0;
      this.chunkSent = true;
      setTimeout(() => { this.chunkSent = false; }, this.chunkBeepDuration);
      this.inactiveTimer = null;
    }, this.delayDuration);
  }

  // Encode recordedSamples as a WAV Blob and send it over the WebSocket.
  async sendRecordedAudio() {
    if (this.isSending) {
      console.log('Already sending audio, skipping.');
      return;
    }
    if (this.recordedSamples.length) {
      this.isSending = true;
      try {
        const wavBlob = encodeWAV(this.recordedSamples, this.sampleRate);
        console.log('Sending chunk', this.chunkNumber, wavBlob);
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          const arrayBuffer = await wavBlob.arrayBuffer();
          this.ws.send(arrayBuffer);
          console.log('Chunk sent over WebSocket.');
        } else {
          console.error('WebSocket is not connected.');
        }
      } catch (error) {
        console.error('Error sending recorded audio:', error);
      } finally {
        this.chunkNumber++;
        this.isSending = false;
        this.recordedSamples = [];
      }
    }
  }
}