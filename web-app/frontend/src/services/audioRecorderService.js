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
        this.thresholdPercentage = 0.1;
        this.sensitivity = {activity: 0.5, reduced: 0.5};
        this.delayDuration = 250; // ms (not used in this implementation)
        this.forceSendDuration = 60000; // 60 seconds fallback
        this.fps = 60;
        this.inactiveTimer = null;
        this.delayTimer = null;
        this.forceSendTimer = null;
        this.silenceTimer = null; // tracks period of silence before sending.
        this.chunkBeepDuration = 250; // ms
        this.chunkSent = false;

        // How long the silence delay is before we consider sending (in ms)
        this.silence_duration = 500;

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
            console.log("Setting up microphone");
            this.audioStream = await navigator.mediaDevices.getUserMedia({audio: true});
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }
            this.sampleRate = this.audioContext.sampleRate;
            const source = this.audioContext.createMediaStreamSource(this.audioStream);

            this.analyser = this.audioContext.createAnalyser();
            source.connect(this.analyser);
            this.bufferLength = this.analyser.frequencyBinCount;
            this.dataArray = new Uint8Array(this.bufferLength);

            await this.audioContext.audioWorklet.addModule('/atlas/audio/processor.js')
                .catch((error) => {
                    console.error('Error loading AudioWorkletProcessor:', error);
                    this.updateStatus({error: true, lastErrorMessage: 'Failed to load audio processor'});
                });
            this.audioWorkletNode = new AudioWorkletNode(this.audioContext, 'recorder-processor');
            source.connect(this.audioWorkletNode);

            this.preBufferSize = Math.floor(this.preBufferDuration * this.sampleRate);
            this.preBuffer = new Float32Array(this.preBufferSize);
            this.preBufferIndex = 0;

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
            this.updateStatus({error: true, lastErrorMessage: 'Failed to access microphone'});
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
        const preBufferData = this.preBuffer.slice(0, this.preBufferIndex);
        this.recordedSamples.push(...preBufferData);
        this.preBufferIndex = this.preBufferSize;
        this.startReactivationLoop();

        // Commented out periodic transcription.
        // this.transcriptionInterval = setInterval(() => {
        //   if (this.recordedSamples.length > 0) {
        //     this.sendRecordedAudio();
        //   }
        // }, 10000);

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
        const loop = () => {
            if (this.isRecording) {
                this.analyser.getByteTimeDomainData(this.dataArray);
                this.checkThresholdCondition();
                requestAnimationFrame(loop);
            }
        };
        loop();
    }

    // New implementation using a silence timer with a minimum chunk duration.
    checkThresholdCondition() {
        const center = 128;
        const centerThreshold = center * this.thresholdPercentage;
        const reducedThreshold = centerThreshold * this.sensitivity.reduced;
        const minVal = Math.min(...this.dataArray);
        const maxVal = Math.max(...this.dataArray);
        const isSilent = (Math.abs(maxVal - center) < reducedThreshold &&
            Math.abs(minVal - center) < reducedThreshold);

        if (isSilent) {
            // Record when silence first occurs.
            if (this.silenceStartTime === null) {
                this.silenceStartTime = Date.now();
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
                            console.log("Silence detected and chunk duration (" + duration.toFixed(2) + "s) meets minimum, sending audio chunk");
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
            // Speech is detected.
            this.hasSpoken = true;
            // Reset silence start and longSilence flag.
            this.silenceStartTime = null;
            this.longSilence = false;
            if (this.silenceTimer) {
                clearTimeout(this.silenceTimer);
                this.silenceTimer = null;
            }
        }
    }

    // Optional forceSendChunk method remains unchanged.
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

    // Updated sendRecordedAudio: adjust overlap based on silence length.
    async sendRecordedAudio() {
        if (this.isSending) {
            console.log('Already sending audio, skipping.');
            return;
        }

        if (this.recordedSamples.length) {
            this.isSending = true;
            try {
                // deprecated: sending base64
                // const float32Array = new Float32Array(this.recordedSamples);
                //         const base64Audio = arrayBufferToBase64(float32Array.buffer);
                //         const audioBlob = this.b64toBlob(base64Audio, 'audio/wav');
                //         const formData = new FormData();
                //         formData.append('file', audioBlob, 'recorded.wav');
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