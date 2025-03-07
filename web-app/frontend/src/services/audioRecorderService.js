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
    this.pendingChunks = new Set();
    
    // Connection status
    this.connectionStatus = {
      connected: false,
      connecting: false,
      error: null,
      lastErrorMessage: null,
      reconnectAttempts: 0,
      maxReconnectAttempts: 3
    };

    // Recording/reactivation settings
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

    // Callback for incoming transcription responses and status updates
    this.onTranscription = null;
    this.onStatusChange = null;
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
          this.updateStatus({ error: true, lastErrorMessage: 'Failed to load audio processor' });
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
      this.updateStatus({ error: true, lastErrorMessage: 'Failed to access microphone' });
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
    if (!this.connectionStatus.connected) {
      this.updateStatus({ 
        error: true, 
        lastErrorMessage: 'Cannot start recording: WebSocket not connected' 
      });
      return;
    }
    
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
    if (this.inactiveTimer) { clearTimeout(this.inactiveTimer); this.inactiveTimer = null; }
    if (this.delayTimer) { clearTimeout(this.delayTimer); this.delayTimer = null; }
    if (this.forceSendTimer) { clearTimeout(this.forceSendTimer); this.forceSendTimer = null; }
    await this.sendRecordedAudio();
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
    if (this.connectionStatus.connecting) {
      return;
    }
    
    this.updateStatus({ connecting: true, error: false });
    
    try {
      // Get JWT token from cookies
      const token = this.getCookie('auth_token');
      
      // Add token to URL as query parameter if available
      const wsUrl = token ? `${url}?token=${encodeURIComponent(token)}` : url;
      
      this.ws = new WebSocket(wsUrl);
      
      this.ws.onopen = () => { 
        console.log('WebSocket connection established.');
        this.updateStatus({ connected: true, connecting: false, error: false });
        // Reset reconnect attempts on successful connection
        this.connectionStatus.reconnectAttempts = 0;
      };

      // Listen for responses from the backend.
      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // If the backend returns a transcription, forward it via the callback.
          if (data.transcription) {
            if (this.onTranscription) {
              this.onTranscription(data.transcription);
            }
          }
          if (data.chunk_id) {
            console.log('Received response for chunk_id', data.chunk_id);
            this.pendingChunks.delete(data.chunk_id);
            if (this.pendingChunks.size === 0) {
              this.flushCookieQueue();
            }
          }
          // Handle authentication errors
          if (data.error && data.error === 'authentication_failed') {
            this.updateStatus({ 
              error: true, 
              connected: false, 
              lastErrorMessage: 'Authentication failed. Please log in again.' 
            });
          }
        } catch (e) {
          console.error('Error parsing WebSocket message:', e);
          this.updateStatus({ 
            error: true, 
            lastErrorMessage: 'Error processing server response' 
          });
        }
      };

      this.ws.onerror = (error) => { 
        console.error('WebSocket error:', error); 
        this.updateStatus({ 
          error: true, 
          connected: false, 
          lastErrorMessage: 'Connection error' 
        });
      };
      
      this.ws.onclose = (event) => { 
        console.log('WebSocket connection closed.', event.code, event.reason);
        
        this.updateStatus({ 
          connected: false, 
          connecting: false 
        });
        
        // Attempt to reconnect if not closed intentionally
        if (event.code !== 1000 && event.code !== 1001) {
          this.attemptReconnect();
        }
      };
    } catch (error) {
      console.error('Error establishing WebSocket connection:', error);
      this.updateStatus({ 
        error: true, 
        connected: false, 
        connecting: false,
        lastErrorMessage: 'Failed to establish connection' 
      });
    }
  }
  
  attemptReconnect() {
    if (this.connectionStatus.reconnectAttempts < this.connectionStatus.maxReconnectAttempts) {
      this.connectionStatus.reconnectAttempts++;
      const delay = Math.pow(2, this.connectionStatus.reconnectAttempts) * 1000; // Exponential backoff
      
      console.log(`Attempting to reconnect in ${delay/1000} seconds (attempt ${this.connectionStatus.reconnectAttempts})`);
      this.updateStatus({ 
        connecting: false, 
        lastErrorMessage: `Connection lost. Reconnecting in ${delay/1000} seconds...` 
      });
      
      setTimeout(() => {
        if (!this.connectionStatus.connected && !this.connectionStatus.connecting) {
          this.connectWebSocket(this.ws.url.split('?')[0]); // Remove any query params
        }
      }, delay);
    } else {
      this.updateStatus({ 
        error: true,
        connecting: false,
        lastErrorMessage: 'Failed to reconnect after multiple attempts. Please reload the page.' 
      });
    }
  }

  updateStatus(statusUpdate) {
    this.connectionStatus = { ...this.connectionStatus, ...statusUpdate };
    
    if (this.onStatusChange) {
      this.onStatusChange(this.connectionStatus);
    }
  }
  
  disconnectWebSocket() {
    if (this.ws) {
      this.ws.close(1000, "Disconnected by user");
      this.updateStatus({ connected: false, connecting: false });
    }
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
        this.forceSendChunk('max');
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

  forceSendChunk(reason) {
    console.log(`Force–sending chunk due to ${reason}`);
    this.sendRecordedAudio();
    if (this.forceSendTimer) { clearTimeout(this.forceSendTimer); this.forceSendTimer = null; }
    this.chunkSent = true;
    setTimeout(() => { this.chunkSent = false; }, this.chunkBeepDuration);
    this.isActive = false;
  }

  // Updated sendRecordedAudio() sends the current recordedSamples via WebSocket.
  async sendRecordedAudio() {
    if (this.isSending) {
      console.log('Already sending audio, skipping.');
      return;
    }
    
    if (!this.connectionStatus.connected) {
      this.updateStatus({ 
        error: true, 
        lastErrorMessage: 'Cannot send audio: WebSocket not connected' 
      });
      return;
    }
    
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
        
        // Get JWT token from cookies and add to payload if available
        const token = this.getCookie('auth_token');
        if (token) {
          payload.token = token;
        }
        
        console.log('Sending chunk', this.chunkNumber);
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify(payload));
          console.log('Chunk sent over WebSocket.');
          this.pendingChunks.add(this.chunkNumber);
        } else {
          const errorMsg = 'WebSocket is not connected.';
          console.error(errorMsg);
          this.updateStatus({ error: true, lastErrorMessage: errorMsg });
        }
      } catch (error) {
        console.error('Error sending recorded audio:', error);
        this.updateStatus({ 
          error: true, 
          lastErrorMessage: 'Failed to send audio data' 
        });
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
          // Get JWT token from cookies
          const token = this.getCookie('auth_token');
          
          for (let payload of queue) {
            // Add token to each payload if available
            if (token) {
              payload.token = token;
            }
            
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
              this.ws.send(JSON.stringify(payload));
              console.log('Flushed queued chunk: chunk_id', payload.chunk_id);
              this.pendingChunks.add(payload.chunk_id);
            } else {
              const errorMsg = 'WebSocket is not connected. Cannot flush cookie queue.';
              console.error(errorMsg);
              this.updateStatus({ error: true, lastErrorMessage: errorMsg });
              break;
            }
          }
          this.deleteCookie(cookieName);
        }
      } catch (e) {
        console.error('Error parsing chunk queue cookie:', e);
        this.updateStatus({ 
          error: true, 
          lastErrorMessage: 'Error processing queued audio chunks' 
        });
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