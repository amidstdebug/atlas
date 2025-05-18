// src/services/audioRecorderService.js
import {encodeWAV} from '@/methods/utils/audioUtils';

export class AudioRecorderService {
    constructor(options = {}) {
        // Set your API server URL, including port. You can override via options.
        this.apiUrl = options.apiUrl || "http://localhost:5002";

        // Recording settings
        this.sampleRate = 48000;
        this.preBufferDuration = options.preBufferDuration || 0.4; // seconds to retain before recording starts
        this.preBufferSize = null;
        this.preBuffer = null;
        this.preBufferIndex = 0;
        this.recordedSamples = [];
        this.isRecording = false;
        this.isSending = false;
        this.transcriptionInterval = null;

        this.minChunkDuration = 5;
        this.hasSpoken = false;
        this.overlapDuration = options.overlapDuration || 1; // in seconds (overlap to retain if silence is short)

        // New properties to track silence duration.
        this.silenceStartTime = null;
        this.longSilence = false;

        // Recording/reactivation settings
        this.thresholdPercentage = 0.02;
        this.sensitivity = {activity: 0.5, reduced: 0.5};
        this.delayDuration = 250; // ms (not used in this implementation)

        // How long the silence delay is before we consider sending (in ms)
        this.silence_duration = 1200;

        this.forceSendDuration = 30000; // 30 seconds fallback


        this.fps = 60;
        this.inactiveTimer = null;
        this.delayTimer = null;
        this.forceSendTimer = null;
        this.silenceTimer = null; // tracks period of silence before sending.
        this.chunkBeepDuration = 250; // ms
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

        // Throttle logging to every 500ms
        this.lastLogTime = 0;
    }

    async setupAudio() {
        try {
            console.log("Setting up high-quality raw microphone input");
            // Request raw audio with preferred constraints
            this.audioStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 48000,        // Request sample rate (may be ignored by some browsers)
                    channelCount: 1,          // mono (or adjust as needed)
                    noiseSuppression: false,  // Disable noise suppression
                    echoCancellation: false   // Disable echo cancellation
                }
            });

            // Create an AudioContext with the desired sample rate
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 48000
            });
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }

            // Set the sample rate from the AudioContext and initialize preBuffer
            this.sampleRate = this.audioContext.sampleRate;
            this.preBufferSize = Math.floor(this.preBufferDuration * this.sampleRate);
            this.preBuffer = new Float32Array(this.preBufferSize);
            this.preBufferIndex = 0;

            // Create a MediaStream source
            const source = this.audioContext.createMediaStreamSource(this.audioStream);

            // Initialize the analyser for silence detection
            this.analyser = this.audioContext.createAnalyser();
            this.bufferLength = this.analyser.frequencyBinCount;
            this.dataArray = new Uint8Array(this.bufferLength);

            // Connect the source to both the analyser and the AudioWorklet
            source.connect(this.analyser);

            // Load the processor module (ensure this processor doesn't perform extra processing)
            await this.audioContext.audioWorklet.addModule('/atlas/audio/processor.js')
                .catch((error) => {
                    console.error('Error loading AudioWorkletProcessor:', error);
                    this.updateStatus({error: true, lastErrorMessage: 'Failed to load audio processor'});
                });

            // Create the worklet node to capture raw audio data
            this.audioWorkletNode = new AudioWorkletNode(this.audioContext, 'recorder-processor');
            // Connect the source also to the worklet node
            source.connect(this.audioWorkletNode);

            // Capture audio data.
            this.audioWorkletNode.port.onmessage = (event) => {
                const audioData = event.data;
                if (audioData.length > 0) {
                    // If not recording yet, store in preBuffer
                    if (!this.isRecording) {
                        this.storeInPreBuffer(audioData);
                    }
                    // Once recording has started, push data into recordedSamples.
                    if (this.isRecording) {
                        this.recordedSamples.push(...audioData);
                    }
                }
            };

            console.log("Audio setup complete with sample rate:", this.sampleRate);
        } catch (error) {
            console.error('Error in setupAudio:', error);
            this.updateStatus({error: true, lastErrorMessage: 'Failed to access microphone'});
        }
    }

    storeInPreBuffer(audioData) {
        // If preBuffer is null (shouldn't happen after setupAudio), initialize it on the fly.
        if (!this.preBuffer) {
            console.warn("preBuffer is null in storeInPreBuffer(), initializing on the fly.");
            this.preBufferSize = Math.floor(this.preBufferDuration * this.sampleRate);
            this.preBuffer = new Float32Array(this.preBufferSize);
            this.preBufferIndex = 0;
        }
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

        // Guard: if preBuffer is null, initialize it.
        if (!this.preBuffer) {
            console.warn("preBuffer is null in startRecording(), initializing on the fly.");
            this.preBufferSize = Math.floor(this.preBufferDuration * this.sampleRate);
            this.preBuffer = new Float32Array(this.preBufferSize);
            this.preBufferIndex = 0;
        }

        // Append any pre-buffered audio into recordedSamples.
        const preBufferData = this.preBuffer.slice(0, this.preBufferIndex);
        this.recordedSamples.push(...preBufferData);
        // Set preBufferIndex to max so further data will overwrite old data.
        this.preBufferIndex = this.preBufferSize;

        this.startReactivationLoop();

        // Set a maximum duration fallback (force send)
        this.forceSendTimer = setTimeout(() => {
            const duration = this.recordedSamples.length / this.sampleRate;
            if (this.hasSpoken && duration >= this.minChunkDuration) {
                console.log("Force-sending chunk due to max duration with speech present. Duration:", duration.toFixed(2) + "s");
                this.sendRecordedAudio();
            } else {
                console.log("Force send skipped due to prolonged silence or insufficient speech. Duration:", duration.toFixed(2) + "s");
            }
            this.forceSendTimer = null;
        }, this.forceSendDuration);
    }

    async stopRecording() {
        this.isRecording = false;
        if (this.transcriptionInterval) {
            clearInterval(this.transcriptionInterval);
            this.transcriptionInterval = null;
        }
        if (this.inactiveTimer) {
            clearTimeout(this.inactiveTimer);
            this.inactiveTimer = null;
        }
        if (this.delayTimer) {
            clearTimeout(this.delayTimer);
            this.delayTimer = null;
        }
        if (this.forceSendTimer) {
            clearTimeout(this.forceSendTimer);
            this.forceSendTimer = null;
        }
        if (this.silenceTimer) {
            clearTimeout(this.silenceTimer);
            this.silenceTimer = null;
        }
        if (this.recordedSamples.length > 0) {
            await this.sendRecordedAudio();
        }
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
        if (this.silenceTimer) {
            clearTimeout(this.silenceTimer);
            this.silenceTimer = null;
        }
        if (this.forceSendTimer) {
            clearTimeout(this.forceSendTimer);
            this.forceSendTimer = null;
        }
        this.chunkSent = false;
    }

    startReactivationLoop() {
        // This loop uses the analyser to check for silence and reactivation.
        const loop = () => {
            if (this.isRecording) {
                if (this.analyser && this.dataArray) {
                    this.analyser.getByteTimeDomainData(this.dataArray);
                    this.checkThresholdCondition();
                }
                requestAnimationFrame(loop);
            }
        };
        loop();
    }

    checkThresholdCondition() {
        // Throttle logging to every 500ms
        const now = Date.now();
        const center = 128;
        const centerThreshold = center * this.thresholdPercentage;
        const reducedThreshold = centerThreshold * this.sensitivity.reduced;
        const minVal = Math.min(...this.dataArray);
        const maxVal = Math.max(...this.dataArray);
        const isSilent = (Math.abs(maxVal - center) < reducedThreshold &&
            Math.abs(minVal - center) < reducedThreshold);

        if (isSilent) {
            if (now - this.lastLogTime >= 500) {
                console.log("Silence detected");
                this.lastLogTime = now;
            }
            if (this.silenceStartTime === null) {
                this.silenceStartTime = now;
            }
            if (this.hasSpoken) {
                if (!this.silenceTimer) {
                    this.silenceTimer = setTimeout(() => {
                        const duration = this.recordedSamples.length / this.sampleRate;
                        const silenceElapsed = Date.now() - this.silenceStartTime;
                        if (silenceElapsed > 2000) { // if silence is longer than 2 seconds
                            this.longSilence = true;
                        }
                        if (duration >= this.minChunkDuration) {
                            console.log("Silence maintained for", silenceElapsed, "ms and duration (" + duration.toFixed(2) + "s) meets minimum, sending audio chunk");
                            this.sendRecordedAudio();
                            this.hasSpoken = false;
                        } else {
                            console.log("Silence detected, but chunk duration (" + duration.toFixed(2) + "s) is less than minimum (" + this.minChunkDuration + "s); waiting for more audio.");
                        }
                        this.silenceTimer = null;
                        this.silenceStartTime = null;
                    }, this.silence_duration);
                }
            }
        } else {
            if (!this.hasSpoken && now - this.lastLogTime >= 500) {
                console.log("Speech detected");
                this.lastLogTime = now;
            }
            this.hasSpoken = true;
            this.silenceStartTime = null;
            this.longSilence = false;
            if (this.silenceTimer) {
                clearTimeout(this.silenceTimer);
                this.silenceTimer = null;
            }
        }
    }

    forceSendChunk(reason) {
        console.log(`Force-sending chunk due to ${reason}`);
        this.sendRecordedAudio();
        if (this.forceSendTimer) {
            clearTimeout(this.forceSendTimer);
            this.forceSendTimer = null;
        }
        this.chunkSent = true;
        setTimeout(() => {
            this.chunkSent = false;
        }, this.chunkBeepDuration);
    }

    async sendRecordedAudio() {
        if (this.isSending) {
            console.log('Already sending audio, skipping.');
            return;
        }

        if (this.recordedSamples.length) {
            this.isSending = true;
            try {
                // Use encodeWAV to properly encode the recorded samples
                const wavBlob = encodeWAV(this.recordedSamples, this.sampleRate);
                const formData = new FormData();
                formData.append('file', wavBlob, 'recorded.wav');

                const token = this.getCookie('auth_token');

                const response = await fetch(`${this.apiUrl}/transcribe`, {
                    method: 'POST',
                    headers: {
                        ...(token ? {'Authorization': `Bearer ${token}`} : {})
                    },
                    body: formData,
                    credentials: 'include'
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    console.error("Audio server error:", errorText);
                    if (this.onStatusChange) {
                        this.onStatusChange({error: true, lastErrorMessage: errorText});
                    }
                } else {
                    const result = await response.json();
                    const transcription = result.transcription || '';
                    if (this.onTranscription) {
                        this.onTranscription(transcription);
                    }
                }
            } catch (error) {
                console.error('Error sending recorded audio:', error);
                if (this.onStatusChange) {
                    this.onStatusChange({error: true, lastErrorMessage: 'Failed to send audio data'});
                }
            } finally {
                this.isSending = false;
                // If long silence was detected, clear the buffer entirely (no overlap).
                if (this.longSilence) {
                    this.recordedSamples = [];
                    this.longSilence = false;
                } else {
                    // Otherwise, retain the last few seconds (prefix overlap).
                    const overlapSamples = Math.floor(this.sampleRate * this.overlapDuration);
                    if (this.recordedSamples.length > overlapSamples) {
                        this.recordedSamples = this.recordedSamples.slice(-overlapSamples);
                    }
                }
            }
        }
    }

    // --- Cookie Helper ---
    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    // --- Helper functions ---
    b64toBlob(b64Data, contentType = 'audio/wav') {
        const byteCharacters = atob(b64Data);
        const byteArrays = [];
        for (let offset = 0; offset < byteCharacters.length; offset += 512) {
            const slice = byteCharacters.slice(offset, offset + 512);
            const byteNumbers = new Array(slice.length);
            for (let i = 0; i < slice.length; i++) {
                byteNumbers[i] = slice.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            byteArrays.push(byteArray);
        }
        return new Blob(byteArrays, {type: contentType});
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