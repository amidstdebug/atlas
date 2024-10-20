<template>
  <!-- Main container for the component -->
  <div class="container">
    <!-- Container for the waveform canvas and overlay -->
    <div class="canvas-container">
      <!-- Canvas element to draw the waveform -->
      <canvas ref="waveform"></canvas>
      <!-- Grey Translucent Overlay displayed when not recording -->
      <div v-if="showOverlay" class="overlay"></div>
      <!-- Live Record Button, displayed when not recording -->
      <el-button
          :style="{ color: liveRecordColor }"
          v-if="showLiveRecordButton"
          class="live-record-button centered-button same-width-button"
          @click="startRecording"
      >
        <el-icon class="icon-group">
          <MicrophoneIcon/>
        </el-icon>
        {{ recordingButton }}
      </el-button>
    </div>

    <!-- Row containing control buttons -->
    <el-row class="button-row">
      <!-- Stop Recording Button, displayed when recording -->
      <el-button
          v-if="showStopButton"
          class="stop-button centered-button same-width-button"
          @click="stopRecording"
      >
        {{ stopRecordingButton }}
      </el-button>
      <!-- Activation Status Button, indicates whether recording is active -->
      <el-button
          :class="['statusButton', 'no-click', isActive ? 'active' : 'inactive']"
      >
        Activated
      </el-button>
      <!-- Chunk Sent Indicator Button, indicates whether a chunk has been sent -->
      <el-button
          :class="['chunkSentButton', 'no-click', chunkSent ? 'red' : 'grey']"
      >
        Chunk Sent
      </el-button>
    </el-row>
  </div>
</template>


<script>
// Import necessary modules and components
import {resizeCanvas} from '@/methods/waveform/setupCanvas';
import {updateMinMax} from '@/methods/utils/updateMinMax';
import {updateTimers} from '@/methods/utils/updateTimers';
import {encodeWAV} from '@/methods/utils/audioUtils';
import {saveBlobLocally} from '@/methods/utils/fileUtils';
import {
  drawWaveformLine,
  drawMinMaxLines,
  drawActivationThresholdLines,
  updateRollingBuffer
} from "@/methods/utils/canvasUtils";
import Cookies from 'js-cookie';
import apiClient from '@/router/apiClient';
import {Microphone} from '@element-plus/icons-vue';
import {typeWriterMultiple} from '@/methods/utils/typeWriter'; // Import the enhanced typeWriterMultiple function
import {tabConfigurations} from '@/config/canvasConfig'; // Adjust the path as necessary
export default {
  name: 'CanvasLayout',
  // Register components used in the template
  components: {
    MicrophoneIcon: Microphone,
  },
  // Define component props
  props: {
    liveRecordColor: {
      type: String,
      default: '#29353C',
    },
    activeTab: {
      type: String,
    },
  },
  watch: {
    activeTab(newTab) {
      this.handleActiveTabChange(newTab);
    },
  },
  // Component data properties
  data() {
    return {
      recordingButton: 'Start Recording',
      stopRecordingButton: 'Stop Recording',
      // Initial transcription text
      transcription: 'This is where the live transcriptions will appear...',
      // Backend endpoint URI
      backendURI: '/transcribe',
      // Threshold percentage for activation detection
      thresholdPercentage: 0.1,
      // Sensitivity settings for activity detection
      sensitivity: {
        activity: 0.5,
        reduced: 0.5,
      },
      // Recording time trackers
      recordingTime: 0,
      delayTime: 0,
      reactivationsLeft: 1,
      // Duration settings
      delayDuration: 250, // in milliseconds
      forceSendDuration: 4000, // in milliseconds
      // Canvas elements
      canvas: null,
      canvasCtx: null,
      // UI elements
      activateButton: null,
      chunkSentButton: null,
      recordingTimeDisplay: null,
      delayTimeDisplay: null,
      reactivationsLeftDisplay: null,
      // Audio analysis
      analyser: null,
      bufferLength: null,
      dataArray: null,
      rollingBuffer: null,
      totalSlices: null,
      slicesFor4Seconds: null,
      activationThreshold: null,
      // Frame rate and offsets
      fps: 60,
      verticalOffset: 120,
      // Timers
      inactiveTimer: null,
      resetTimer: null,
      delayTimer: null,
      // Reactivation counters
      reactivationCount: 0,
      maxReactivations: 1,
      // Beep duration for chunk sent indication
      chunkBeepDuration: 250, // in milliseconds
      // Recording state
      isRecording: false,
      recordingStartTime: null,
      delayStartTime: null,
      conditionCounter: 0,
      isActive: false,
      chunkSent: false,
      chunkNumber: 1,
      forceSendTimer: null,
      // Audio processing
      audioContext: null,
      audioWorkletNode: null,
      recordedSamples: [],
      sampleRate: 48000,
      audioStream: null,
      preBufferDuration: 0.55, // in seconds
      preBufferSize: null,
      preBuffer: null,
      preBufferIndex: 0,
      // UI visibility flags
      showOverlay: true,
      showLiveRecordButton: true,
      showStopButton: false,
      // Flag to prevent multiple sends
      isSending: false,
      typingSpeed: 12,
      // Cancellation functions for typewriter effects
      cancelTypingFunctions: [], // Array to hold cancellation functions
    };
  },
  // Lifecycle hook - called when component is mounted
  mounted() {
    this.setupCanvas();
  },
  methods: {
    /**
     * Handle changes to the activeTab prop.
     * @param {String} newTab - The new activeTab value.
     */
    handleActiveTabChange(newTab) {
      // Cancel existing typewriter effects
      this.cancelTypingFunctions.forEach((cancelFn) => cancelFn());
      this.cancelTypingFunctions = [];

      // Get the configuration for the new tab
      const config = tabConfigurations[newTab];

      if (config && config.buttons) {
        // Clear existing button labels
        this.recordingButton = '';
        this.stopRecordingButton = '';

        // Define typing tasks for buttons
        const typingTasks = [
          {
            text: config.buttons.recordingButton,
            typingSpeed: this.typingSpeed, // Adjust as needed
            onUpdate: (currentText) => {
              this.recordingButton = currentText;
            },
            onComplete: () => {
              // Optional: Actions after recordingButton typing completes
            },
          },
          {
            text: config.buttons.stopRecordingButton,
            typingSpeed: this.typingSpeed, // Adjust as needed
            onUpdate: (currentText) => {
              this.stopRecordingButton = currentText;
            },
            onComplete: () => {
              // Optional: Actions after stopRecordingButton typing completes
            },
          },
        ];

        // Start typewriter effects
        this.cancelTypingFunctions = typeWriterMultiple(typingTasks);
      } else {
        console.warn(`No configuration found for activeTab: ${newTab}`);
      }
    },
    /**
     * Start recording audio and initialize audio processing.
     */
    startRecording() {
      // Optional: Log the buffer states for debugging
      console.log(
          'Starting new recording. Recorded Samples Length:',
          this.recordedSamples.length
      );
      console.log('PreBuffer Index:', this.preBufferIndex);

      this.initializeAudio();
      this.showOverlay = false;
      this.showLiveRecordButton = false;
      this.showStopButton = true;
    },
    /**
     * Stop recording audio and reset the recording state.
     */
    async stopRecording() {
      this.showOverlay = true;
      this.showLiveRecordButton = true;
      this.showStopButton = false;
      if (this.audioContext && this.audioContext.state !== 'suspended') {
        await this.audioContext.suspend();
      }
      this.resetState();
    },
    /**
     * Initialize audio context and start audio processing.
     */
    initializeAudio() {
      const initialize = async () => {
        if (this.audioContext) {
          if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
          }
        } else {
          await this.setupAudio();
          this.drawWaveform();
          this.startUpdatingTimers();
        }
      };
      initialize();
    },
    /**
     * Update timer values for recording and delay times.
     * @param {number} recordingTime - Current recording time in milliseconds.
     * @param {number} delayTime - Current delay time in milliseconds.
     * @param {number} reactivationsLeft - Number of reactivations left.
     */
    updateTimerValues(recordingTime, delayTime, reactivationsLeft) {
      this.recordingTime = recordingTime;
      this.delayTime = delayTime;
      this.reactivationsLeft = reactivationsLeft;
    },
    /**
     * Start updating the timers for recording and delays.
     */
    startUpdatingTimers() {
      const update = () => {
        updateTimers(
            this.isRecording,
            this.recordingStartTime,
            this.delayStartTime,
            this.delayDuration,
            this.maxReactivations,
            this.reactivationCount,
            this.updateTimerValues
        );
        requestAnimationFrame(update);
      };
      update();
    },
    /**
     * Set up the canvas for waveform drawing.
     */
    setupCanvas() {
      const canvas = this.$refs.waveform;
      if (!canvas) {
        console.error("Canvas element with ref 'waveform' not found.");
        return;
      }
      const canvasCtx = canvas.getContext('2d');
      if (!canvasCtx) {
        console.error('Failed to get 2D context from canvas.');
        return;
      }
      this.canvas = canvas;
      this.canvasCtx = canvasCtx;
      resizeCanvas(this.canvas, this.canvasCtx);
    },
    /**
     * Set up audio context, audio nodes, and start processing audio.
     */
    async setupAudio() {
      try {
        console.log('Connecting audio nodes');
        // Get user media (microphone input)
        this.audioStream = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });
        this.audioContext = new (window.AudioContext ||
            window.webkitAudioContext)();

        if (this.audioContext.state === 'suspended') {
          await this.audioContext.resume();
        }

        this.sampleRate = this.audioContext.sampleRate;
        const source = this.audioContext.createMediaStreamSource(
            this.audioStream
        );

        // Create an analyser node for audio visualization
        this.analyser = this.audioContext.createAnalyser();
        source.connect(this.analyser);
        this.bufferLength = this.analyser.frequencyBinCount;
        this.dataArray = new Uint8Array(this.bufferLength);

        // Initialize rolling buffer for waveform visualization
        this.totalSlices = 20 * this.fps;
        this.rollingBuffer = new Uint8Array(
            this.totalSlices * this.bufferLength
        ).fill(128);
        this.slicesFor4Seconds = 4 * this.fps;
        this.activationThreshold = this.sensitivity['activity'] * this.fps;

        // Load audio worklet processor for recording
        await this.audioContext.audioWorklet
            .addModule('/atlas/audio/processor.js')
            .catch((error) => {
              console.error('Error loading AudioWorkletProcessor:', error);
            });

        this.audioWorkletNode = new AudioWorkletNode(
            this.audioContext,
            'recorder-processor'
        );
        source.connect(this.audioWorkletNode);

        // Initialize pre-buffer for retaining audio before activation
        this.preBufferSize = Math.floor(
            this.preBufferDuration * this.sampleRate
        );
        this.preBuffer = new Float32Array(this.preBufferSize);
        this.preBufferIndex = 0;

        // Handle incoming audio data from the worklet processor
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
    },
    /**
     * Store incoming audio data into the pre-buffer.
     * @param {Float32Array} audioData - Audio data samples.
     */
    storeInPreBuffer(audioData) {
      const dataLength = audioData.length;
      if (dataLength + this.preBufferIndex > this.preBufferSize) {
        const overflow = dataLength + this.preBufferIndex - this.preBufferSize;
        // Shift the buffer to discard the oldest data
        this.preBuffer.copyWithin(0, overflow, this.preBufferIndex);
        this.preBufferIndex -= overflow;
      }
      this.preBuffer.set(audioData, this.preBufferIndex);
      this.preBufferIndex += dataLength;
    },
    /**
     * Clear the canvas for waveform drawing.
     */
    clearCanvas() {
      this.canvasCtx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    },
    /**
     * Draw the waveform line on the canvas.
     */
    drawWaveformLine() {
      drawWaveformLine({
        canvasCtx: this.canvasCtx,
        canvasWidth: this.canvas.width,
        canvasHeight: this.canvas.height,
        rollingBuffer: this.rollingBuffer,
        bufferLength: this.bufferLength,
        totalSlices: this.totalSlices,
        verticalOffset: this.verticalOffset,
        strokeStyle: '#00FFCC', // Optional: Customize as needed
        lineWidth: 2,            // Optional: Customize as needed
      });
    },
    /**
     * Draw minimum and maximum lines on the waveform for visualization.
     */
    drawMinMaxLines() {
      const {min: normalizedMinValue, max: normalizedMaxValue} = updateMinMax(
          this.rollingBuffer,
          this.bufferLength,
          this.slicesFor4Seconds,
          this.canvas,
          this.verticalOffset
      );

      drawMinMaxLines({
        canvasCtx: this.canvasCtx,
        canvasWidth: this.canvas.width,
        normalizedMinValue,
        normalizedMaxValue,
        minLineColor: '#21219a', // Optional: Customize as needed
        maxLineColor: '#f83030', // Optional: Customize as needed
        lineWidth: 1,             // Optional: Customize as needed
      });
    },
    /**
     * Draw activation threshold lines on the waveform.
     */
    drawActivationThresholdLines() {
      const centerY = this.canvas.height / 2 - this.verticalOffset;
      const activationThresholdY =
          this.canvas.height * (this.thresholdPercentage / 2);

      drawActivationThresholdLines({
        canvasCtx: this.canvasCtx,
        canvasWidth: this.canvas.width,
        centerY,
        activationThresholdY,
        strokeStyle: '#919b07',    // Optional: Customize as needed
        lineWidth: 1,               // Optional: Customize as needed
      });
    },
    /**
     * Check if the audio signal is within the activation threshold.
     * If conditions are met, activate or deactivate recording accordingly.
     */
    checkThresholdCondition() {
      const centerY = this.canvas.height / 2 - this.verticalOffset;
      const centerThreshold = this.canvas.height * this.thresholdPercentage;
      let reducedThreshold = centerThreshold * this.sensitivity['reduced'];

      const {min: normalizedMinValue, max: normalizedMaxValue} = updateMinMax(
          this.rollingBuffer,
          this.bufferLength,
          this.slicesFor4Seconds,
          this.canvas,
          this.verticalOffset
      );

      const withinThreshold =
          Math.abs(normalizedMaxValue - centerY) < reducedThreshold &&
          Math.abs(normalizedMinValue - centerY) < reducedThreshold;

      if (withinThreshold) {
        this.conditionCounter++;

        if (this.conditionCounter >= this.activationThreshold && this.isActive) {
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
    },
    /**
     * Activate recording when the audio signal exceeds the threshold.
     */
    activateRecording() {
      console.log('Activating recording');

      this.isActive = true;
      this.isRecording = true;
      this.recordingStartTime = Date.now();
      this.delayStartTime = null;

      if (this.delayTimer) {
        clearTimeout(this.delayTimer);
        this.delayTimer = null;
      }

      // Include the retained pre-buffer data in the new recording
      const preBufferData = this.preBuffer.slice(0, this.preBufferIndex);
      this.recordedSamples.push(...preBufferData);

      // Reset preBufferIndex to allow new data to be written after retained data
      this.preBufferIndex = this.preBufferSize;

      // Set a timer to force send the chunk after a certain duration
      this.forceSendTimer = setTimeout(() => {
        this.forceSendChunk('time');
      }, this.forceSendDuration);

      this.recordingTime = 0;

      this.chunkSent = false;
    },
    /**
     * Deactivate recording when the audio signal falls below the threshold.
     */
    deactivateRecording() {
      console.log('Deactivating recording');

      this.isActive = false;
      this.isRecording = false;
      this.delayStartTime = Date.now();

      this.reactivationCount++;
      this.reactivationsLeft = this.maxReactivations - this.reactivationCount;

      this.delayTime = 0;

      console.log(`Audio stopped | Reactivation count: ${this.reactivationCount}`);

      if (this.forceSendTimer) {
        clearTimeout(this.forceSendTimer);
        this.forceSendTimer = null;
      }

      // Start a delay timer before considering the recording inactive
      this.delayTimer = setTimeout(() => {
        this.startInactiveTimer();
      }, this.delayDuration);

      this.chunkSent = false;
    },
    /**
     * Reset the recording state and clear audio buffers.
     */
    resetState() {
      // Reset recording state variables
      this.isRecording = false;
      this.isActive = false;
      this.reactivationCount = 0;
      this.recordingStartTime = null;
      this.delayStartTime = null;
      this.conditionCounter = 0;
      this.chunkSent = false;

      // Clear audio buffers but retain the last preBufferDuration seconds
      this.clearAudioBuffers();
    },
    /**
     * Force send the recorded audio chunk due to specified reason.
     * @param {string} reason - Reason for forcing the chunk send ('max' or 'time').
     */
    forceSendChunk(reason) {
      console.log(`Chunk sent due to ${reason}`);

      this.sendChunkToConsole();

      // Reset the state after sending the chunk
      if (this.forceSendTimer) {
        clearTimeout(this.forceSendTimer);
        this.forceSendTimer = null;
      }

      this.chunkSent = true;

      // Indicate that the chunk was sent (e.g., for UI feedback)
      this.resetTimer = setTimeout(() => {
        this.chunkSent = false;
      }, this.chunkBeepDuration);

      this.isActive = false;
    },
    /**
     * Send the recorded audio chunk to the backend API.
     */
    async sendChunkToConsole() {
      if (this.isSending) {
        console.log('Already sending a chunk, skipping send.');
        return;
      }

      if (this.recordedSamples.length) {
        this.isSending = true; // Start sending
        try {
          // Encode recorded samples into WAV format
          const wavBlob = encodeWAV(this.recordedSamples, this.sampleRate);
          console.log('Chunk', this.chunkNumber, 'sent:', wavBlob);

          // Optionally save the WAV file locally (for debugging)
          // saveBlobLocally(wavBlob, `chunk_${this.chunkNumber}.wav`);

          this.clearAudioBuffers();

          // Prepare form data for API request
          const formData = new FormData();
          formData.append('file', wavBlob, `chunk_${this.chunkNumber}.wav`);
          console.log('Sending WAV blob:', wavBlob);

          // Send the audio file to the backend API
          const response = await apiClient.post(this.backendURI, formData);

          if (response && response.status === 200) {
            const contentType = response.headers['content-type'];
            let data;

            if (contentType.includes('application/json')) {
              data = response.data;
            } else {
              data = response.data;
            }

            console.log('Transcription result:', data);
            if (
                data.transcription &&
                data.transcription !== 'False activation'
            ) {
              // Emit an event with the transcription result
							console.log("Emitted:", data.transcription)
              this.$emit('transcription-received', data.transcription);
            }
          } else {
            throw new Error('Network response was not ok.');
          }
        } catch (error) {
          console.error('Error sending the chunk:', error);
        } finally {
          // Clear audio buffers but retain the last preBufferDuration seconds
          this.chunkNumber++;
          this.isSending = false; // Reset sending flag
        }
      }
    },
    /**
     * Clear audio buffers while retaining the last preBufferDuration seconds.
     */
    clearAudioBuffers() {
      // Clear the recorded samples
      this.recordedSamples = [];

      // Retain the last 'preBufferDuration' seconds of audio
      if (this.preBuffer) {
        const retainSamples = this.preBufferSize; // Number of samples to retain
        const start = this.preBufferIndex - retainSamples;
        const end = this.preBufferIndex;

        if (start < 0) {
          // Handle buffer wrap-around
          const part1 = this.preBuffer.slice(
              start + this.preBuffer.length,
              this.preBuffer.length
          );
          const part2 = this.preBuffer.slice(0, end);
          this.preBuffer.fill(0);
          this.preBuffer.set(part1, 0);
          this.preBuffer.set(part2, part1.length);
        } else {
          const retainedBuffer = this.preBuffer.slice(start, end);
          this.preBuffer.fill(0); // Clear the buffer
          this.preBuffer.set(retainedBuffer, 0); // Retain the last 'preBufferSize' samples
        }

        // Reset preBufferIndex to the end of the retained data
        this.preBufferIndex = Math.min(end - start, this.preBufferSize);
      }

      // Reset recording state variables
      this.isRecording = false;
      this.isActive = false;
      this.reactivationCount = 0;
      this.recordingStartTime = null;
      this.delayStartTime = null;
      this.conditionCounter = 0;
      this.chunkSent = false;
    },
    /**
     * Start an inactive timer to determine when to send the audio chunk after inactivity.
     */
    startInactiveTimer() {
      if (this.inactiveTimer) {
        return;
      }

      this.inactiveTimer = setTimeout(() => {
        this.sendChunkToConsole();
        this.reactivationCount = 0;
        this.chunkSent = true;

        this.resetTimer = setTimeout(() => {
          this.resetTimer = null;
          this.chunkSent = false;
        }, this.chunkBeepDuration);

        this.inactiveTimer = null;
      }, this.delayDuration);
    },
    /**
     * Update the rolling buffer with new audio data for visualization.
     */
    updateRollingBuffer() {
      updateRollingBuffer({
        analyser: this.analyser,
        dataArray: this.dataArray,
        rollingBuffer: this.rollingBuffer,
        bufferLength: this.bufferLength,
      });
    },
    /**
     * Main loop for drawing the waveform and checking activation conditions.
     */
    drawWaveform() {
      requestAnimationFrame(this.drawWaveform);
      if (!this.analyser) {
        return;
      }

      this.updateRollingBuffer();
      this.clearCanvas();
      this.drawWaveformLine();
      this.drawMinMaxLines();
      this.drawActivationThresholdLines();
      this.checkThresholdCondition();
    },
    /**
     * Save WAV audio blob locally (for debugging purposes).
     * @param {Blob} blob - WAV audio blob.
     * @param {string} fileName - File name for the saved audio.
     */
    saveWavLocally(blob, fileName) {
      const url = URL.createObjectURL(blob);

      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = fileName;

      document.body.appendChild(a);
      a.click();

      URL.revokeObjectURL(url);
      document.body.removeChild(a);
    },
  },
  beforeUnmount() {
    // Clean up any pending typing effects when the component is destroyed
    this.cancelTypingFunctions.forEach((cancelFn) => cancelFn());

    // Additional cleanup if necessary
    if (this.audioContext) {
      this.audioContext.close();
    }
  },
}
</script>
<style scoped>
/* Global body styles */
body {
  background-color: #121212;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  margin: 0;
  flex-direction: column;
}

/* Container for canvas and overlay */
.canvas-container {
  position: relative;
  /* Uncomment and adjust width and height as needed */
  /* width: 600px; /* Or any desired width */
  /* height: 400px; /* Or any desired height */
}

/* Styles for canvas and overlay */
canvas,
.overlay {
  width: 100%;
  height: 100%;
  display: block;
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

canvas {
  border: 1px solid #333;
  border-radius: 10px;
}

.overlay {
  position: absolute;
  top: 0;
  left: 0;
  background-color: rgba(41, 53, 60, 0.71);
  border-radius: 10px;
}

/* Positioning for the live record button */
.live-record-button {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

/* Styles for the stop button */
.stop-button {
  /* Adjust styles as needed */
  margin-right: 10px;
}

/* Common styles for status and chunk sent buttons */
.statusButton,
.chunkSentButton {
  padding: 10px 20px;
  font-size: 15px;
  border-radius: 8px;
  margin: 10px;
  color: white;
}

/* Main container styles */
.container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  width: 100%;
  margin-left: 20px;
  margin-top: 45px;
}

/* Styles for the button row */
.button-row {
  display: flex;
  align-items: center;
}

/* Disable pointer events for certain buttons */
.no-click {
  pointer-events: none;
}

/* Background colors for status indicators */
.inactive {
  background-color: #555 !important;
}

.active {
  background-color: #4caf50 !important;
}

/* Background colors for chunk sent indicator */
.grey {
  background-color: #555 !important;
}

.red {
  background-color: #ff6347 !important;
}

/* Styles for timer text */
.timer {
  color: #fff;
  font-size: 18px;
  margin-top: 10px;
}

/* Text color utility class */
.text-color {
  color: black;
}

/* Utility class for centering buttons */
.centered-button {
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 10px;
  box-sizing: border-box;
}

/* Utility class to ensure buttons have the same width */
.same-width-button {
  min-width: 130px;
  max-width: 130px;
}
</style>