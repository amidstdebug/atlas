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

        // Properties to track silence duration.
        this.silenceStartTime = null;
        this.longSilence = false;

        this.forceSendDuration = 30000; // 30 seconds fallback
        // How long the silence delay is before we consider sending (in ms)
        this.silence_duration = 1200;
        // Calibrated dB value for silence detection. Adjust as needed.
        this.calibratedDb = -1; // e.g., -50 dB represents baseline silence

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

        // Property to track downloaded payloads for local evaluation (download first 3) – comment out if not needed
        this.payloadDownloadCount = 0;

        // Flag to indicate a pending send request
        this.pendingSend = false;

        // Last time (in ms) we logged the current state.
        this.lastLogTime = 0;
    }

    async setupAudio() {
        try {
            console.log("Setting up microphone");
            this.audioStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 48000,
                    channelCount: 1,
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false,
                },
            });
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            if (this.audioContext.state === "suspended") {
                await this.audioContext.resume();
            }
            this.sampleRate = this.audioContext.sampleRate;
            const source = this.audioContext.createMediaStreamSource(this.audioStream);

            this.analyser = this.audioContext.createAnalyser();
            source.connect(this.analyser);
            this.bufferLength = this.analyser.frequencyBinCount;
            this.dataArray = new Uint8Array(this.bufferLength);

            await this.audioContext.audioWorklet
                .addModule("/atlas/audio/processor.js")
                .catch((error) => {
                    console.error("Error loading AudioWorkletProcessor:", error);
                    this.updateStatus({
                        error: true,
                        lastErrorMessage: "Failed to load audio processor",
                    });
                });
            this.audioWorkletNode = new AudioWorkletNode(this.audioContext, "recorder-processor");
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
            console.error("Error in setupAudio:", error);
            this.updateStatus({
                error: true,
                lastErrorMessage: "Failed to access microphone",
            });
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
        } else if (this.audioContext.state === "suspended") {
            await this.audioContext.resume();
        }
        this.isRecording = true;
        const preBufferData = this.preBuffer.slice(0, this.preBufferIndex);
        this.recordedSamples.push(...preBufferData);
        this.preBufferIndex = this.preBufferSize;
        this.startReactivationLoop();

        // Set a maximum duration fallback (force send)
        this.forceSendTimer = setTimeout(() => {
            const duration = this.recordedSamples.length / this.sampleRate;
            if (this.hasSpoken && duration >= this.minChunkDuration) {
                console.log(
                    "Force-sending chunk due to max duration with speech present. Duration:",
                    duration.toFixed(2) + "s"
                );
                this.sendRecordedAudio();
            } else {
                console.log(
                    "Force send skipped due to prolonged silence or insufficient speech. Duration:",
                    duration.toFixed(2) + "s"
                );
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
        // Only send recorded audio if speech was detected
        if (this.recordedSamples.length > 0 && this.hasSpoken) {
            console.log('ghost sent?')
            await this.sendRecordedAudio();
        } else {
            console.log("No speech detected, not sending audio chunk.");
        }
        this.closeAudio();
        this.resetState();
    }

    closeAudio() {
        if (this.audioStream) {
            this.audioStream.getTracks().forEach((track) => track.stop());
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
        this.pendingSend = false;
        this.hasSpoken = false;
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

    /**
     * Modified speech/silence detection:
     * - Uses the live instantaneous dB value computed from the current buffer.
     * - Determines if the current dB value deviates from the calibrated baseline by more than 20%
     *   (using 20% of the absolute value of the calibrated dB).
     * - If the deviation exceeds the 20% window, it's considered speech; otherwise, silence.
     */
    checkThresholdCondition() {
        const center = 128;
        let sumSq = 0;
        for (let i = 0; i < this.dataArray.length; i++) {
            const diff = this.dataArray[i] - center;
            sumSq += diff * diff;
        }
        const rms = Math.sqrt(sumSq / this.dataArray.length);
        const currentDb = rms > 0 ? 20 * Math.log10(rms) : -Infinity;

        const windowThreshold = Math.abs(this.calibratedDb) * 0.2;
        const delta = currentDb - this.calibratedDb;

        const now = Date.now();
        if (now - this.lastLogTime >= 1000) {
            if (delta > windowThreshold) {
                console.log(
                    `Speech detected (Current dB: ${currentDb.toFixed(2)}, Delta: ${delta.toFixed(2)} > Window: ${windowThreshold.toFixed(2)}) at ${new Date().toLocaleTimeString()}`
                );
            } else {
                console.log(
                    `Silence detected (Current dB: ${currentDb.toFixed(2)}, Delta: ${delta.toFixed(2)} <= Window: ${windowThreshold.toFixed(2)}) at ${new Date().toLocaleTimeString()}`
                );
            }
            this.lastLogTime = now;
        }

        if (delta > windowThreshold) {
            // Speech detected.
            this.hasSpoken = true;
            this.silenceStartTime = null;
            if (this.silenceTimer) {
                clearTimeout(this.silenceTimer);
                this.silenceTimer = null;
            }
        } else {
            // Silence detected.
            if (this.silenceStartTime === null) {
                this.silenceStartTime = Date.now();
            }
            if (this.hasSpoken) {
                if (!this.silenceTimer) {
                    this.silenceTimer = setTimeout(() => {
                        const duration = this.recordedSamples.length / this.sampleRate;
                        // Calculate average amplitude from the recorded samples.
                        const avgAmplitude =
                            this.recordedSamples.reduce((sum, val) => sum + Math.abs(val), 0) /
                            this.recordedSamples.length;
                        // Only send if the duration is long enough and there is significant audio energy.
                        if (duration >= this.minChunkDuration && avgAmplitude > 0.02) {
                            console.log("sending audio chunk with speech detected");
                            this.sendRecordedAudio();
                        } else {
                            console.log("Not sending audio chunk, insufficient speech energy");
                        }
                        this.hasSpoken = false;
                        this.silenceTimer = null;
                        this.silenceStartTime = null;
                    }, this.silence_duration);
                }
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

    // Revised sendRecordedAudio with extra guard to avoid sending when no speech was detected.
    async sendRecordedAudio() {
        // New check: do not send if no speech was detected.
        if (!this.hasSpoken) {
            console.log("No speech detected, aborting sendRecordedAudio call.");
            return;
        }
        if (this.isSending) {
            this.pendingSend = true;
            return;
        }
        this.isSending = true;
        try {
            const wavBlob = encodeWAV(this.recordedSamples, this.sampleRate);
            const formData = new FormData();
            formData.append("file", wavBlob, "recorded.wav");

            const token = this.getCookie("auth_token");

            const response = await fetch(`${this.apiUrl}/transcribe`, {
                method: "POST",
                headers: {
                    ...(token ? {Authorization: `Bearer ${token}`} : {}),
                },
                body: formData,
                credentials: "include",
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error("Audio server error:", errorText);
                if (this.onStatusChange) {
                    this.onStatusChange({error: true, lastErrorMessage: errorText});
                }
            } else {
                const result = await response.json();
                const transcription = result.transcription || "";
                if (this.onTranscription) {
                    this.onTranscription(transcription);
                }
            }
        } catch (error) {
            console.error("Error sending recorded audio:", error);
            if (this.onStatusChange) {
                this.onStatusChange({error: true, lastErrorMessage: "Failed to send audio data"});
            }
        } finally {
            this.isSending = false;
            // If a send was pending while we were busy, check again before sending.
            if (this.pendingSend) {
                this.pendingSend = false;
                if (this.hasSpoken) {
                    console.log('ghost sent 2')
                    await this.sendRecordedAudio();
                } else {
                    console.log("No speech detected on pending send, aborting.");
                }
            } else {
                // Retain only the overlap samples in the buffer.
                const overlapSamples = Math.floor(this.sampleRate * this.overlapDuration);
                if (this.recordedSamples.length > overlapSamples) {
                    this.recordedSamples = this.recordedSamples.slice(-overlapSamples);
                }
            }
        }
    }

    // --- Cookie Helper ---
    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(";").shift();
        return null;
    }

    // --- Helper functions ---
    b64toBlob(b64Data, contentType = "audio/wav") {
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
    let binary = "";
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
}