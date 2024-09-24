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
<!--    <el-row>-->
<!--      <div class="timer text-color">Recording Time: {{ recordingTime }}s</div>-->
<!--    </el-row>-->
<!--    <el-row>-->
<!--      <div class="timer text-color">Delay Time Left: {{ delayTime }}s</div>-->
<!--    </el-row>-->
<!--    <el-row>-->
<!--      <div class="timer text-color">-->
<!--        Re-activations Left: {{ reactivationsLeft }}-->
<!--      </div>-->
<!--    </el-row>-->
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
  margin-top:45px;
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
import {resizeCanvas} from '@/methods/waveform/setupCanvas'
import {setupAudioContext} from "@/methods/recording/recording";
import {updateMinMax} from '@/methods/utils/updateMinMax';
import {updateTimers} from '@/methods/utils/updateTimers';
import {FFmpeg} from '@ffmpeg/ffmpeg';

export default {
  data() {
    return {
      transcription: 'This is where the live transcriptions will appear...',
      backendURI: 'https://jwong.dev/api/transcribe',
      thresholdPercentage: 0.20, // sensitivity percentage
      sensitivity: {
        'activity': 0.5, // the higher, the less sensitive
        'reduced': 0.5, // the higher, the less sensitive
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
      mediaRecorder: null,
      recordedChunks: [],


    };
  },
  mounted() {
    this.$nextTick(() => {
      this.setupCanvas();
      this.setupAudio();
      this.setupMediaRecorder();
      this.drawWaveform();
      this.startUpdatingTimers();
    });
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
        console.error("Failed to get 2D context from canvas.");
        return;
      }

      // Store the canvas and context in the Vue instance
      this.canvas = canvas;
      this.canvasCtx = canvasCtx;

      // Retrieve and store button and display elements using Vue's ref system
      this.recordingTimeDisplay = this.$refs.recordingTime;
      this.delayTimeDisplay = this.$refs.delayTime;
      this.reactivationsLeftDisplay = this.$refs.reactivationsLeft;

      // Resize the canvas for optimal display
      resizeCanvas(this.canvas, this.canvasCtx);
    },

    /**
     * Initializes the audio context and analyser for capturing real-time audio data
     */
    setupAudio() {
      // Set up the audio context and analyser node
      const {analyser, audioContext} = setupAudioContext(this.drawWaveform);

      // Create a gain node to boost the volume
      const gainNode = audioContext.createGain();
      gainNode.gain.value = 1.2; // Increase the value to boost the volume (1.0 = no boost, >1.0 = volume boost)

      // Connect the analyser to the gain node, but do not connect to destination (no playback)
      analyser.connect(gainNode);

      // Do not connect gainNode to audioContext.destination to avoid playback
      // gainNode.connect(audioContext.destination); // Remove or comment this out

      // Store the analyser and buffer properties in the component
      this.analyser = analyser;
      this.bufferLength = analyser.frequencyBinCount / 2;
      this.dataArray = new Uint8Array(this.bufferLength);

      // Initialize the rolling buffer and slices for waveform processing
      this.totalSlices = 20 * this.fps;
      this.rollingBuffer = new Float32Array(this.totalSlices * this.bufferLength).fill(128);
      this.slicesFor4Seconds = 4 * this.fps;
      this.activationThreshold = this.sensitivity['activity'] * this.fps;
    },

    /**
     * Sets up the MediaRecorder to handle microphone audio recording
     */
    async setupMediaRecorder() {
      // Request microphone access and define audio constraints
      const constraints = {
        audio: {
          sampleRate: 48000,
          echoCancellation: false,
          noiseSuppression: false,
          channelCount: 2
        }
      };

      // Capture the audio stream from the user's microphone
      const stream = await navigator.mediaDevices.getUserMedia(constraints);

      // Initialize the MediaRecorder with the captured audio stream
      this.mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm; codecs=opus',
        audioBitsPerSecond: 192000 // 192 kbps for high-quality audio
      });
      // Warm up the media recorder
      this.mediaRecorder.start();
      this.mediaRecorder.stop();
      // Set up event handler for capturing audio chunks when data is available
      this.mediaRecorder.ondataavailable = event => {
        if (event.data.size > 0) {
          // Store the recorded chunk in the recordedChunks array
          this.recordedChunks.push(event.data);
        } else {
          console.log('No data available:', event);
        }
      };
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
      a.download = fileName;  // Set the desired file name

      // Append the anchor to the DOM and trigger the download
      document.body.appendChild(a);
      a.click();

      // Revoke the object URL and clean up the DOM after the download
      URL.revokeObjectURL(url);
      document.body.removeChild(a);
    },
    /**
     * Converts a WebM audio file to WAV format using FFmpeg
     * @param {Blob} blob - The WebM audio blob to be converted
     * @returns {Promise<Blob>} - A promise that resolves with the WAV blob
     */
    async convertWebmToWav(blob) {
      try {
        const ffmpeg = new FFmpeg({
          corePath: '/libs/ffmpeg-core.js',  // Path to the locally stored core file
        });

        // Load the FFmpeg core into memory
        await ffmpeg.load();
        console.log('ffmpeg loaded successfully');

        // Read the WebM blob data and write it into FFmpeg's virtual filesystem
        const webmFileData = await blob.arrayBuffer();
        await ffmpeg.writeFile('input.webm', new Uint8Array(webmFileData));

        // Execute FFmpeg command to convert WebM to WAV with high-quality settings
        await ffmpeg.exec(['-i', 'input.webm', '-ar', '48000', '-ac', '2', '-b:a', '320k', 'output.wav']);

        // Read the converted WAV data back into a blob
        const wavData = await ffmpeg.readFile('output.wav');
        const wavBlob = new Blob([wavData.buffer], {type: 'audio/wav'});

        // Clean up the FFmpeg instance and return the WAV blob
        ffmpeg.terminate();
        return wavBlob;
      } catch (e) {
        console.error('could not load ffmpeg core');
      }
    }
    ,
    /**
     * Updates the rolling buffer with the latest audio data from the AnalyserNode
     */
    updateRollingBuffer() {
      // Fetch time-domain audio data from the analyser
      this.analyser.getByteTimeDomainData(this.dataArray);

      // Shift the rolling buffer to make room for new data
      this.rollingBuffer.set(this.rollingBuffer.subarray(this.bufferLength), 0);

      // Append the latest audio data to the end of the rolling buffer
      this.rollingBuffer.set(this.dataArray, this.rollingBuffer.length - this.bufferLength);
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
      this.canvasCtx.strokeStyle = '#00FFCC';  // Color of the waveform line
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
      this.canvasCtx.stroke();  // Draw the waveform
    }, /**
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
      this.canvasCtx.strokeStyle = '#919b07';  // Yellow color for threshold lines
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
        this.conditionCounter = 0;  // Reset the counter if the signal exceeds the threshold

        // Clear the inactivity timer if it exists
        if (this.inactiveTimer) {
          clearTimeout(this.inactiveTimer);
          this.inactiveTimer = null;
        }
      }
    }, /**
     * Activates recording by starting the media recorder and updating the UI
     */
    activateRecording() {
      console.log('Activating recording');

      // this.chunkSent = true;
      this.isActive = true;
      this.isRecording = true;
      this.recordingStartTime = Date.now();
      this.delayStartTime = null;

      // Clear any existing timers
      if (this.delayTimer) {
        clearTimeout(this.delayTimer);
        this.delayTimer = null;
      }

      // Start a timer to forcefully send a chunk after the max duration
      this.forceSendTimer = setTimeout(() => {
        this.forceSendChunk('time');
      }, this.forceSendDuration);

      // Update recording time
      this.recordingTime = 0;  // Reset recording time when starting

      // Start the media recorder if it is inactive
      if (this.mediaRecorder.state === 'inactive') {
        this.mediaRecorder.start();
      }
      // Reset chunkSent flag since we are starting a new recording
      this.chunkSent = false;
    },
    /**
     * Deactivates recording by stopping the media recorder and updating the UI
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
    resetState() {
      // Resetting the state
      this.isRecording = false;
      this.isActive = false;
      this.reactivationCount = 0;
      this.recordingStartTime = null;
      this.delayStartTime = null;
      this.conditionCounter = 0;
      this.chunkSent = false;

      // Update the UI (referencing the refs)
      if (this.$refs.recordingTime) {
        this.$refs.recordingTime.textContent = 'Recording Time: 0s';
      }
      if (this.$refs.delayTime) {
        this.$refs.delayTime.textContent = 'Delay Time Left: 0s';
      }
      if (this.$refs.reactivationsLeft) {
        this.$refs.reactivationsLeft.textContent = `Re-activations Left: ${this.maxReactivations}`;
      }


    },
    /**
     * Forces the current chunk to be sent when a threshold or duration limit is reached
     * @param {string} reason - The reason for forcing the chunk to be sent ('max' or 'time')
     */
    forceSendChunk(reason) {
      console.log(`Chunk sent due to ${reason}`);

      // Stop the media recorder to trigger chunk sending
      this.mediaRecorder.stop();

      // After stopping, send the chunk to the console and server
      this.mediaRecorder.onstop = () => {
        this.sendChunkToConsole();
      };

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
        this.chunkSent = false
      }, this.chunkBeepDuration);
      // Mark the chunk as sent and light up the button
      this.isActive = false; // Set button to inactive state
    },
    /**
     * Sends the recorded audio chunk to the backend for transcription
     */
    sendChunkToConsole() {
      if (this.recordedChunks.length) {
        const blob = new Blob(this.recordedChunks, {type: 'audio/webm'});
        console.log('Chunk', this.chunkNumber, 'sent:', blob); // Add log for the chunk

        this.convertWebmToWav(blob).then((wavBlob) => {
          const formData = new FormData();
          formData.append('file', wavBlob, `chunk_${this.chunkNumber}.wav`);
          console.log('Sending WAV blob:', wavBlob); // Log the WAV blob before sending

          // Save the WAV file locally before sending it
          const fileName = `chunk_${this.chunkNumber}.wav`;
          // this.saveWavLocally(wavBlob, fileName);
          const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiYXRsYXN1c2VyIiwiZXhwIjoxNzI2NTg3NjUxfQ.1N7yP-q4NSXO6dnQPhOrBHZXkBXZAb3mg88AQ7XvDS4';
          fetch(this.backendURI, {
            method: 'POST',
            body: formData,
            headers: {
              'Authorization': `Bearer ${token}`, // Add Bearer token to the Authorization header
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
                // Emit the transcription data to the parent component (App.vue)\
                if (data.transcription !== 'false activation') {
                  // this.$emit('transcription-received', data.transcription || 'Transcription failed');
                  this.$emit('transcription-received', data.transcription)
                }
              })
              .catch((error) => {
                console.error('Error sending the chunk:', error); // Log any error
              });
        });

        this.recordedChunks = []; // Clear the array for the next chunk
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
        // Check if the MediaRecorder is currently recording and stop it
        if (this.mediaRecorder.state === 'recording') {
          this.mediaRecorder.stop();
        } else {
          console.log('MediaRecorder is not in recording state:', this.mediaRecorder.state);
        }

        // Set up the 'onstop' event to send the audio chunk when recording stops
        this.mediaRecorder.onstop = () => {
          this.sendChunkToConsole(); // Log and send the chunk data
        };

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

    drawWaveform() {
      requestAnimationFrame(this.drawWaveform);
      this.updateRollingBuffer();
      this.clearCanvas();
      this.drawWaveformLine();
      this.drawMinMaxLines();
      this.drawActivationThresholdLines();
      this.checkThresholdCondition();
    },

  },

};
</script>
