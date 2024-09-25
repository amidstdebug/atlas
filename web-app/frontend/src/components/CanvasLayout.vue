<template>
  <div class="container">
    <canvas ref="waveform"></canvas>
    <el-row class="button-row">
      <!-- Activate Button -->
      <el-button
          :class="['statusButton', 'no-click', isActive ? 'active' : 'inactive']"
      >
        Activated
      </el-button>

      <!-- Chunk Sent Button -->
      <el-button
          :class="['chunkSentButton', 'no-click', chunkSent ? 'red' : 'grey']"
      >
        Chunk Sent
      </el-button>
    </el-row>
  </div>
</template>


<style scoped>
body {
  background-color: #121212;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  margin: 0;
  flex-direction: column;
}

canvas {
  border: 1px solid #333;
  margin-bottom: 20px; /* Add space between canvas and buttons */
}

.statusButton,
.chunkSentButton {
  padding: 10px 20px; /* Reduced padding */
  font-size: 15px; /* Increase font size */
  border-radius: 8px; /* Adjust border-radius for a larger look */
  margin: 10px; /* Increase margin to give more spacing between buttons */
  color: white;
}

.container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  width: 100%; /* Ensures the container spans the full width */
  margin-left: 20px; /* Add margin to the left */
  margin-top: 45px;
}

.no-click {
  pointer-events: none; /* Prevents the button from being clickable */
}

.inactive {
  background-color: #555 !important;
}

.active {
  background-color: #4CAF50 !important;
}


.grey {
  background-color: #555 !important; /* Grey color for the initial state */
}

.red {
  background-color: #FF6347 !important; /* Red color when activated */
}

.timer {
  color: #FFF;
  font-size: 18px;
  margin-top: 10px;
}

.text-color {
  color: black;
}

</style>

<script>
import {resizeCanvas} from '@/methods/waveform/setupCanvas';
import {updateMinMax} from '@/methods/utils/updateMinMax';
import {updateTimers} from '@/methods/utils/updateTimers';

export default {
  data() {
    return {
      transcription: 'This is where the live transcriptions will appear...',
      backendURI: 'https://jwong.dev/api/transcribe',
      thresholdPercentage: 0.20, // sensitivity percentage
      sensitivity: {
        activity: 0.5, // the higher, the less sensitive
        reduced: 0.5, // the higher, the less sensitive
      },
      recordingTime: 0, // Initial recording time
      delayTime: 0, // Initial delay time
      reactivationsLeft: 1, // Initial reactivation count
      delayDuration: 250, // delay in between sending chunks
      forceSendDuration: 8000, // the higher, the longer each chunk is
      canvas: null,
      canvasCtx: null,
      activateButton: null,
      chunkSentButton: null,
      recordingTimeDisplay: null,
      delayTimeDisplay: null,
      reactivationsLeftDisplay: null,
      analyser: null,
      bufferLength: null,
      dataArray: null,
      rollingBuffer: null,
      totalSlices: null,
      slicesFor4Seconds: null,
      activationThreshold: null,
      fps: 60,
      verticalOffset: 60,
      inactiveTimer: null,
      resetTimer: null,
      delayTimer: null,
      reactivationCount: 0,
      maxReactivations: 1,
      chunkBeepDuration: 250,
      isRecording: false,
      recordingStartTime: null,
      delayStartTime: null,
      conditionCounter: 0,
      isActive: false,
      chunkSent: false,
      chunkNumber: 1,
      forceSendTimer: null,
      audioContext: null,
      audioWorkletNode: null,
      recordedSamples: [],
      sampleRate: 48000,
      audioStream: null,
      /* Pre-buffer properties */
      preBufferDuration: 0.3, // Duration in seconds for pre-buffering
      preBufferSize: null,
      preBuffer: null,
      preBufferIndex: 0,
    };
  },
  mounted() {
    this.setupCanvas();
    const initialize = async () => {
      await this.setupAudio(); // Wait for setupAudio to complete
      this.drawWaveform();
      this.startUpdatingTimers();
    };
    initialize();
  },
  methods: {
    updateTimerValues(recordingTime, delayTime, reactivationsLeft) {
      this.recordingTime = recordingTime;
      this.delayTime = delayTime;
      this.reactivationsLeft = reactivationsLeft;
    },
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
     * Sets up the canvas and related DOM elements for drawing the waveform
     */
    setupCanvas() {
      // Retrieve the canvas element using Vue's ref system
      const canvas = this.$refs.waveform;

      // Check if the canvas element exists
      if (!canvas) {
        console.error("Canvas element with ref 'waveform' not found.");
        return;
      }

      // Retrieve the 2D drawing context from the canvas
      const canvasCtx = canvas.getContext('2d');

      // Check if the 2D context is available
      if (!canvasCtx) {
        console.error('Failed to get 2D context from canvas.');
        return;
      }

      // Store the canvas and context in the Vue instance
      this.canvas = canvas;
      this.canvasCtx = canvasCtx;

      // Resize the canvas for optimal display
      resizeCanvas(this.canvas, this.canvasCtx);
    },
    /**
     * Initializes the audio context and sets up the AudioWorkletNode
     */
    async setupAudio() {
      try {
        // Request microphone access
        this.audioStream = await navigator.mediaDevices.getUserMedia({audio: true});

        // Create AudioContext without specifying sample rate
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();

        // Retrieve the actual sample rate
        this.sampleRate = this.audioContext.sampleRate;

        // Create MediaStreamSource
        const source = this.audioContext.createMediaStreamSource(this.audioStream);

        // Set up analyser for visualization
        this.analyser = this.audioContext.createAnalyser();
        source.connect(this.analyser);
        this.bufferLength = this.analyser.frequencyBinCount;
        this.dataArray = new Uint8Array(this.bufferLength);

        // Initialize the rolling buffer and related properties after bufferLength is set
        this.totalSlices = 20 * this.fps;
        this.rollingBuffer = new Uint8Array(this.totalSlices * this.bufferLength).fill(128); // Changed to Uint8Array
        this.slicesFor4Seconds = 4 * this.fps;
        this.activationThreshold = this.sensitivity['activity'] * this.fps;

        // Load the AudioWorkletProcessor
        await this.audioContext.audioWorklet.addModule('audio/processor.js');

        // Create AudioWorkletNode
        this.audioWorkletNode = new AudioWorkletNode(this.audioContext, 'recorder-processor');

        // Connect nodes
        source.connect(this.audioWorkletNode);
        // Uncomment if you want to hear the audio playback
        // this.audioWorkletNode.connect(this.audioContext.destination);

        // Initialize pre-buffer
        this.preBufferSize = this.preBufferDuration * this.sampleRate;
        this.preBuffer = new Float32Array(this.preBufferSize);
        this.preBufferIndex = 0;

        // Handle messages from the processor
        this.audioWorkletNode.port.onmessage = (event) => {
          const audioData = event.data;
          if (audioData.length > 0) {
            // Store audio data in pre-buffer
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
     * Stores audio data in the pre-buffer
     */
    storeInPreBuffer(audioData) {
      const dataLength = audioData.length;
      if (dataLength + this.preBufferIndex > this.preBufferSize) {
        // Shift existing data to make room
        const shiftAmount = dataLength + this.preBufferIndex - this.preBufferSize;
        this.preBuffer.copyWithin(0, shiftAmount, this.preBufferIndex);
        this.preBufferIndex -= shiftAmount;
      }
      // Copy new data into pre-buffer
      this.preBuffer.set(audioData, this.preBufferIndex);
      this.preBufferIndex += dataLength;
    },
    /**
     * Clears the canvas to prepare it for the next frame of the waveform
     */
    clearCanvas() {
      // Clear the entire canvas
      this.canvasCtx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    },
    /**
     * Draws the waveform line on the canvas based on the current rolling buffer data
     */
    drawWaveformLine() {
      this.canvasCtx.lineWidth = 2;
      this.canvasCtx.strokeStyle = '#00FFCC'; // Color of the waveform line
      this.canvasCtx.beginPath();

      const sliceWidth = this.canvas.width / this.totalSlices;
      let x = 0;
      const centerY = this.canvas.height / 2 - this.verticalOffset;

      // Loop through the rolling buffer and plot the waveform points
      for (let i = 0; i < this.rollingBuffer.length; i += this.bufferLength) {
        const v = this.rollingBuffer[i] / 128.0 - 1.0;
        const y = centerY + v * (this.canvas.height / 4);

        if (i === 0) {
          this.canvasCtx.moveTo(x, y);
        } else {
          this.canvasCtx.lineTo(x, y);
        }
        x += sliceWidth;
      }
      this.canvasCtx.stroke(); // Draw the waveform
    },
    /**
     * Draws the min and max value lines on the canvas to indicate signal extremes
     */
    drawMinMaxLines() {
      // Get the normalized min and max values of the current rolling buffer
      const {min: normalizedMinValue, max: normalizedMaxValue} = updateMinMax(
          this.rollingBuffer,
          this.bufferLength,
          this.slicesFor4Seconds,
          this.canvas,
          this.verticalOffset
      );

      // Draw the max value line in red
      this.canvasCtx.strokeStyle = '#f83030';
      this.canvasCtx.lineWidth = 1;
      this.canvasCtx.beginPath();
      this.canvasCtx.moveTo(0, normalizedMaxValue);
      this.canvasCtx.lineTo(this.canvas.width, normalizedMaxValue);
      this.canvasCtx.stroke();

      // Draw the min value line in blue
      this.canvasCtx.strokeStyle = '#21219a';
      this.canvasCtx.beginPath();
      this.canvasCtx.moveTo(0, normalizedMinValue);
      this.canvasCtx.lineTo(this.canvas.width, normalizedMinValue);
      this.canvasCtx.stroke();
    },
    /**
     * Draws activation threshold lines on the canvas to show the boundary for triggering recording
     */
    drawActivationThresholdLines() {
      const centerY = this.canvas.height / 2 - this.verticalOffset;
      const activationThresholdY = this.canvas.height * (this.thresholdPercentage / 2);

      // Draw the upper threshold line
      this.canvasCtx.strokeStyle = '#919b07'; // Yellow color for threshold lines
      this.canvasCtx.beginPath();
      this.canvasCtx.moveTo(0, centerY - activationThresholdY);
      this.canvasCtx.lineTo(this.canvas.width, centerY - activationThresholdY);

      // Draw the lower threshold line
      this.canvasCtx.moveTo(0, centerY + activationThresholdY);
      this.canvasCtx.lineTo(this.canvas.width, centerY + activationThresholdY);
      this.canvasCtx.stroke();
    },
    /**
     * Checks if the waveform data exceeds the activation threshold and controls recording accordingly
     */
    checkThresholdCondition() {
      const centerY = this.canvas.height / 2 - this.verticalOffset;
      const centerThreshold = this.canvas.height * this.thresholdPercentage;
      let reducedThreshold = centerThreshold * this.sensitivity['reduced']; // Make it more responsive to changes

      // Get the current min and max values from the rolling buffer
      const {min: normalizedMinValue, max: normalizedMaxValue} = updateMinMax(
          this.rollingBuffer,
          this.bufferLength,
          this.slicesFor4Seconds,
          this.canvas,
          this.verticalOffset
      );

      // Check if the signal stays within the threshold range
      const withinThreshold =
          Math.abs(normalizedMaxValue - centerY) < reducedThreshold &&
          Math.abs(normalizedMinValue - centerY) < reducedThreshold;

      if (withinThreshold) {
        // Increment the condition counter if the signal is within the threshold
        this.conditionCounter++;

        // If the condition counter exceeds the activation threshold, deactivate recording
        if (this.conditionCounter >= this.activationThreshold && this.isActive) {
          if (this.reactivationCount >= this.maxReactivations) {
            this.forceSendChunk('max');
          } else {
            this.deactivateRecording();
          }
        }
      } else {
        // If the signal exceeds the threshold, activate recording
        if (!this.isActive && !this.chunkSent) {
          this.activateRecording();
        }
        this.conditionCounter = 0; // Reset the counter if the signal exceeds the threshold

        // Clear the inactivity timer if it exists
        if (this.inactiveTimer) {
          clearTimeout(this.inactiveTimer);
          this.inactiveTimer = null;
        }
      }
    },
    /**
     * Activates recording by starting to collect audio data and updating the UI
     */
    activateRecording() {
      console.log('Activating recording');

      this.isActive = true;
      this.isRecording = true;
      this.recordingStartTime = Date.now();
      this.delayStartTime = null;

      // Clear any existing timers
      if (this.delayTimer) {
        clearTimeout(this.delayTimer);
        this.delayTimer = null;
      }

      // Include pre-buffered audio data
      const preBufferData = this.preBuffer.slice(0, this.preBufferIndex);
      this.recordedSamples.push(...preBufferData);

      // Reset pre-buffer index
      this.preBufferIndex = 0;

      // Start a timer to forcefully send a chunk after the max duration
      this.forceSendTimer = setTimeout(() => {
        this.forceSendChunk('time');
      }, this.forceSendDuration);

      // Update recording time
      this.recordingTime = 0; // Reset recording time when starting

      // Reset chunkSent flag since we are starting a new recording
      this.chunkSent = false;
    },
    /**
     * Deactivates recording by stopping the collection of audio data and updating the UI
     */
    deactivateRecording() {
      console.log('Deactivating recording');

      this.isActive = false;
      this.isRecording = false;
      this.delayStartTime = Date.now();

      // Increment the reactivation count
      this.reactivationCount++;
      this.reactivationsLeft = this.maxReactivations - this.reactivationCount; // Update reactivations left

      // Reset delay time left
      this.delayTime = 0;

      console.log(`Audio stopped | Reactivation count: ${this.reactivationCount}`);

      // Clear the force send timer
      if (this.forceSendTimer) {
        clearTimeout(this.forceSendTimer);
        this.forceSendTimer = null;
      }

      // Start a delay timer for reactivation
      this.delayTimer = setTimeout(() => {
        this.startInactiveTimer();
      }, this.delayDuration);

      this.chunkSent = false; // Set button to inactive state
    },
    /**
     * Resets the state after recording is stopped or chunk is sent
     */
    resetState() {
      // Resetting the state
      this.isRecording = false;
      this.isActive = false;
      this.reactivationCount = 0;
      this.recordingStartTime = null;
      this.delayStartTime = null;
      this.conditionCounter = 0;
      this.chunkSent = false;

      // Clear pre-buffer
      this.preBufferIndex = 0;
    },
    /**
     * Forces the current chunk to be sent when a threshold or duration limit is reached
     * @param {string} reason - The reason for forcing the chunk to be sent ('max' or 'time')
     */
    forceSendChunk(reason) {
      console.log(`Chunk sent due to ${reason}`);

      // Process the recorded samples
      this.sendChunkToConsole();

      // Reset the recording state
      this.resetState();

      // Clear the force send timer
      if (this.forceSendTimer) {
        clearTimeout(this.forceSendTimer);
        this.forceSendTimer = null;
      }

      this.chunkSent = true;

      // Reset the chunk sent button after a short beep duration
      this.resetTimer = setTimeout(() => {
        this.chunkSent = false;
      }, this.chunkBeepDuration);
      // Mark the chunk as sent and light up the button
      this.isActive = false; // Set button to inactive state
    },
    /**
     * Sends the recorded audio chunk to the backend for transcription
     */
    sendChunkToConsole() {
      if (this.recordedSamples.length) {
        const wavBlob = this.encodeWAV(this.recordedSamples, this.sampleRate);
        console.log('Chunk', this.chunkNumber, 'sent:', wavBlob);

        const formData = new FormData();
        formData.append('file', wavBlob, `chunk_${this.chunkNumber}.wav`);
        console.log('Sending WAV blob:', wavBlob);

        // Save the WAV file locally before sending it
        // const fileName = `chunk_${this.chunkNumber}.wav`;
        // this.saveWavLocally(wavBlob, fileName);
        const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiYXRsYXN1c2VyIiwiZXhwIjoxNzI2NTg3NjUxfQ.1N7yP-q4NSXO6dnQPhOrBHZXkBXZAb3mg88AQ7XvDS4';
        fetch(this.backendURI, {
          method: 'POST',
          body: formData,
          headers: {
            Authorization: `Bearer ${token}`, // Add Bearer token to the Authorization header
          },
        })
            .then((response) => {
              if (response.ok) {
                return response.headers.get('content-type').includes('application/json')
                    ? response.json()
                    : response.text();
              }
              throw new Error('Network response was not ok.');
            })
            .then((data) => {
              console.log('Transcription result:', data); // Log the transcription result
              // Emit the transcription data to the parent component (App.vue)
              if (data.transcription !== 'false activation') {
                this.$emit('transcription-received', data.transcription);
              }
            })
            .catch((error) => {
              console.error('Error sending the chunk:', error); // Log any error
            });

        this.recordedSamples = []; // Clear the array for the next chunk
      }
      this.chunkNumber++;
    },
    startInactiveTimer() {
      // Check if the inactive timer is already running
      if (this.inactiveTimer) {
        return;
      }

      // Set the inactive timer
      this.inactiveTimer = setTimeout(() => {
        // Process the recorded samples
        this.sendChunkToConsole();

        // Reset the reactivation count
        this.reactivationCount = 0;

        this.chunkSent = true;

        // Set the reset timer to revert the button's appearance
        this.resetTimer = setTimeout(() => {
          this.resetTimer = null; // Clear the reset timer
          this.chunkSent = false;
        }, this.chunkBeepDuration);

        // Clear the inactive timer after it finishes
        this.inactiveTimer = null;
      }, this.delayDuration);
    },
    /**
     * Updates the rolling buffer with the latest audio data from the analyser
     */
    updateRollingBuffer() {
      // Get the latest frequency data from the analyser
      this.analyser.getByteTimeDomainData(this.dataArray);

      // Shift the rolling buffer to make room for new data
      this.rollingBuffer.copyWithin(0, this.bufferLength);

      // Append the new data at the end of the rolling buffer
      this.rollingBuffer.set(this.dataArray, this.rollingBuffer.length - this.bufferLength);
    },
    drawWaveform() {
      requestAnimationFrame(this.drawWaveform);
      // Ensure that analyser is initialized
      if (!this.analyser) {
        return; // Exit if analyser is not ready
      }

      this.updateRollingBuffer();
      this.clearCanvas();
      this.drawWaveformLine();
      this.drawMinMaxLines();
      this.drawActivationThresholdLines();
      this.checkThresholdCondition();
    },
    /**
     * Encodes the recorded samples into a WAV Blob
     * @param {Float32Array} samples - The recorded audio samples
     * @param {number} sampleRate - The sample rate of the audio context
     * @returns {Blob} - The WAV file blob
     */
    encodeWAV(samples, sampleRate) {
      const buffer = new ArrayBuffer(44 + samples.length * 2);
      const view = new DataView(buffer);

      /* RIFF identifier */
      this.writeString(view, 0, 'RIFF');
      /* file length */
      view.setUint32(4, 36 + samples.length * 2, true);
      /* RIFF type */
      this.writeString(view, 8, 'WAVE');
      /* format chunk identifier */
      this.writeString(view, 12, 'fmt ');
      /* format chunk length */
      view.setUint32(16, 16, true);
      /* sample format (raw) */
      view.setUint16(20, 1, true);
      /* channel count */
      view.setUint16(22, 1, true);
      /* sample rate */
      view.setUint32(24, sampleRate, true);
      /* byte rate (sample rate * block align) */
      view.setUint32(28, sampleRate * 2, true);
      /* block align (channel count * bytes per sample) */
      view.setUint16(32, 2, true);
      /* bits per sample */
      view.setUint16(34, 16, true);
      /* data chunk identifier */
      this.writeString(view, 36, 'data');
      /* data chunk length */
      view.setUint32(40, samples.length * 2, true);

      // Write the PCM samples
      let offset = 44;
      for (let i = 0; i < samples.length; i++, offset += 2) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      }

      return new Blob([view], {type: 'audio/wav'});
    },
    /**
     * Helper function to write strings to the DataView
     */
    writeString(view, offset, string) {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    },
    /**
     * Saves the recorded audio chunk as a WAV file locally
     * @param {Blob} blob - The audio blob to be saved
     * @param {string} fileName - The name of the file to save
     */
    saveWavLocally(blob, fileName) {
      // Create a temporary URL for the audio blob
      const url = URL.createObjectURL(blob);

      // Create a hidden anchor element to trigger the download
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = fileName; // Set the desired file name

      // Append the anchor to the DOM and trigger the download
      document.body.appendChild(a);
      a.click();

      // Revoke the object URL and clean up the DOM after the download
      URL.revokeObjectURL(url);
      document.body.removeChild(a);
    },
  },
};
</script>
