// src/services/audioRecorderService.js

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

    // For tracking pending chunks
    this.pendingChunks = new Set(); // holds chunk ids for which we have not received a response

    // Recording/reactivation settings (unchanged)
    this.thresholdPercentage = 0.1;
    this.sensitivity = { activity: 0.5, reduced: 0.5 };
    this.delayDuration = 250; // ms
    this.forceSendDuration = 8000; // ms
    this.fps = 60;
    this.inactiveTimer = null;
    this.delayTimer = null;
    this.forceSendTimer = null;
    this.reactivationCount = 0;
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

      // Create an analyser node for reactivation
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

      // Initialize pre–buffer
      this.preBufferSize = Math.floor(this.preBufferDuration * this.sampleRate);
      this.preBuffer = new Float32Array(this.preBufferSize);
      this.preBufferIndex = 0;

      // Save incoming audio data to the pre–buffer and (if recording) recordedSamples
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

  async stopRecording() {
    this.isRecording = false;
    // Clear pending timers
    if (this.inactiveTimer) { clearTimeout(this.inactiveTimer); this.inactiveTimer = null; }
    if (this.delayTimer) { clearTimeout(this.delayTimer); this.delayTimer = null; }
    if (this.forceSendTimer) { clearTimeout(this.forceSendTimer); this.forceSendTimer = null; }
    // Send any remaining audio chunk
    await this.sendRecordedAudio();
    // Close microphone and audio context
    this.closeAudio();
    this.resetState();
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
    this.pendingChunks.clear();
  }

  connectWebSocket(url) {
    this.ws = new WebSocket(url);
    this.ws.onopen = () => { console.log('WebSocket connection established.'); };

    // Listen for responses from the backend
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.chunk_id) {
          console.log('Received response for chunk_id', data.chunk_id);
          // Remove the pending chunk since we got the response.
          this.pendingChunks.delete(data.chunk_id);
          // Flush any queued chunks stored in cookies if there are none pending now.
          if (this.pendingChunks.size === 0) {
            this.flushCookieQueue();
          }
        }
      } catch (e) {
        console.error('Error parsing WebSocket message:', e);
      }
    };

    this.ws.onerror = (error) => { console.error('WebSocket error:', error); };
    this.ws.onclose = () => { console.log('WebSocket connection closed.'); };
  }

  startReactivationLoop() {
    const loop = () => {
      if (this.isRecording) {
        this.analyser.getByteTimeDomainData(this.dataArray);
        this.checkThresholdCondition();
        requestAnimationFrame(loop);
      }
    };
    loop();
  }

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

  activateRecording() {
    console.log('Activating recording (chunk start)');
    this.isActive = true;
    this.recordingStartTime = Date.now();
    if (this.delayTimer) { clearTimeout(this.delayTimer); this.delayTimer = null; }
    const preBufferData = this.preBuffer.slice(0, this.preBufferIndex);
    this.recordedSamples.push(...preBufferData);
    this.preBufferIndex = this.preBufferSize;
    this.forceSendTimer = setTimeout(() => { this.forceSendChunk('time'); }, this.forceSendDuration);
    this.conditionCounter = 0;
    this.chunkSent = false;
  }

  deactivateRecording() {
    console.log('Deactivating recording (chunk end)');
    this.isActive = false;
    this.delayTimer = setTimeout(() => { this.startInactiveTimer(); }, this.delayDuration);
    this.reactivationCount++;
    this.chunkSent = false;
  }

  forceSendChunk(reason) {
    console.log(`Force–sending chunk due to ${reason}`);
    this.sendRecordedAudio();
    if (this.forceSendTimer) { clearTimeout(this.forceSendTimer); this.forceSendTimer = null; }
    this.chunkSent = true;
    setTimeout(() => { this.chunkSent = false; }, this.chunkBeepDuration);
    this.isActive = false;
  }

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

  // Updated sendRecordedAudio() now adds a chunk_id and checks for pending responses.
  async sendRecordedAudio() {
    if (this.isSending) {
      console.log('Already sending audio, skipping.');
      return;
    }
    // If there are pending chunk responses, queue this chunk in the cookie
    if (this.pendingChunks.size > 0) {
      console.log('Previous chunk(s) still pending; queuing new chunk in cookie.');
      if (this.recordedSamples.length) {
        const float32Array = new Float32Array(this.recordedSamples);
        const base64Audio = arrayBufferToBase64(float32Array.buffer);
        const payload = { chunk_id: this.chunkNumber, audio: base64Audio };
        this.addChunkToCookieQueue(payload);
        this.chunkNumber++;
        this.recordedSamples = [];
      }
      return;
    }

    if (this.recordedSamples.length) {
      this.isSending = true;
      try {
        const float32Array = new Float32Array(this.recordedSamples);
        const base64Audio = arrayBufferToBase64(float32Array.buffer);
        const payload = { chunk_id: this.chunkNumber, audio: base64Audio };
        console.log('Sending chunk', this.chunkNumber, payload);
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify(payload));
          console.log('Chunk sent over WebSocket.');
          // Mark this chunk as pending a response.
          this.pendingChunks.add(this.chunkNumber);
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

  // --- Cookie-based Queue Helpers ---
  addChunkToCookieQueue(payload) {
    const cookieName = 'chunkQueue';
    const existing = this.getCookie(cookieName);
    let queue = [];
    if (existing) {
      try {
        queue = JSON.parse(existing);
      } catch (e) {
        queue = [];
      }
    }
    queue.push(payload);
    this.setCookie(cookieName, JSON.stringify(queue), 1);
  }

  flushCookieQueue() {
    const cookieName = 'chunkQueue';
    const existing = this.getCookie(cookieName);
    if (existing) {
      try {
        const queue = JSON.parse(existing);
        if (queue.length > 0) {
          for (let payload of queue) {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
              this.ws.send(JSON.stringify(payload));
              console.log('Flushed queued chunk: chunk_id', payload.chunk_id);
              // Mark the flushed chunk as pending.
              this.pendingChunks.add(payload.chunk_id);
            } else {
              console.error('WebSocket is not connected. Cannot flush cookie queue.');
              break;
            }
          }
          // Once flushed, clear the cookie.
          this.deleteCookie(cookieName);
        }
      } catch (e) {
        console.error('Error parsing chunk queue cookie:', e);
      }
    }
  }

  getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }

  setCookie(name, value, days) {
    let expires = "";
    if (days) {
      const date = new Date();
      date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
      expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "") + expires + "; path=/";
  }

  deleteCookie(name) {
    this.setCookie(name, "", -1);
  }
}

// Helper: converts an ArrayBuffer to a base64 string.
function arrayBufferToBase64(buffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}