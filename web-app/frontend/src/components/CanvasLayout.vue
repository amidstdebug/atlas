<template>
  <div class="container">
    <div class="canvas-container">
      <canvas ref="waveform"></canvas>
      <!-- Grey Translucent Overlay -->
      <div v-if="showOverlay" class="overlay"></div>
      <!-- Live Record Button -->
      <el-button
          :style="{ color: liveRecordColor }"
          v-if="showLiveRecordButton"
          class="live-record-button centered-button same-width-button"
          @click="startRecording"
      >
        <el-icon class="icon-group">
          <MicrophoneIcon/>
        </el-icon>
        Start Recording
      </el-button>
    </div>

    <el-row class="button-row">
      <!-- Stop Recording Button -->
      <el-button
          v-if="showStopButton"
          class="stop-button centered-button same-width-button"
          @click="stopRecording"
      >
        Stop Recording
      </el-button>
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

.canvas-container {
  position: relative;
  //width: 600px; /* Or any desired width */
  //height: 400px; /* Or any desired height */
}

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

.live-record-button {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.stop-button {
  /* Adjust styles as needed */
  margin-right: 10px;
}

.statusButton,
.chunkSentButton {
  padding: 10px 20px;
  font-size: 15px;
  border-radius: 8px;
  margin: 10px;
  color: white;
}

.container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  width: 100%;
  margin-left: 20px;
  margin-top: 45px;
}

.button-row {
  display: flex;
  align-items: center;
}

.no-click {
  pointer-events: none;
}

.inactive {
  background-color: #555 !important;
}

.active {
  background-color: #4CAF50 !important;
}

.grey {
  background-color: #555 !important;
}

.red {
  background-color: #FF6347 !important;
}

.timer {
  color: #FFF;
  font-size: 18px;
  margin-top: 10px;
}

.text-color {
  color: black;
}

.centered-button {
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 10px;
  box-sizing: border-box;
}

.same-width-button {
  min-width: 130px;
  max-width: 130px;
}
</style>

<script>
import {resizeCanvas} from '@/methods/waveform/setupCanvas';
import {updateMinMax} from '@/methods/utils/updateMinMax';
import {updateTimers} from '@/methods/utils/updateTimers';
import Cookies from 'js-cookie';
import apiClient from '@/router/apiClient';
import {Microphone} from "@element-plus/icons-vue";

export default {
  components: {
    MicrophoneIcon: Microphone,
  },
  props: {
    liveRecordColor: {
      type: String,
      default: '#29353C',
    },
  },
  data() {
    return {
      transcription: 'This is where the live transcriptions will appear...',
      backendURI: '/transcribe',
      thresholdPercentage: 0.1,
      sensitivity: {
        activity: 0.5,
        reduced: 0.5,
      },
      recordingTime: 0,
      delayTime: 0,
      reactivationsLeft: 1,
      delayDuration: 250,
      forceSendDuration: 8000,
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
      verticalOffset: 120,
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
      preBufferDuration: 0.4,
      preBufferSize: null,
      preBuffer: null,
      preBufferIndex: 0,
      showOverlay: true,
      showLiveRecordButton: true,
      showStopButton: false,
    };
  },
  mounted() {
    this.setupCanvas();
  },
  methods: {
    startRecording() {
      this.initializeAudio();
      this.showOverlay = false;
      this.showLiveRecordButton = false;
      this.showStopButton = true;
    },
    async stopRecording() {
      this.showOverlay = true;
      this.showLiveRecordButton = true;
      this.showStopButton = false;
      if (this.audioContext && this.audioContext.state !== 'suspended') {
        await this.audioContext.suspend();
      }
      this.resetState();
    },
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
    async setupAudio() {
      try {
        console.log('Connecting audio nodes');
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

        this.totalSlices = 20 * this.fps;
        this.rollingBuffer = new Uint8Array(this.totalSlices * this.bufferLength).fill(128);
        this.slicesFor4Seconds = 4 * this.fps;
        this.activationThreshold = this.sensitivity['activity'] * this.fps;

        await this.audioContext.audioWorklet.addModule('/atlas/audio/processor.js').catch((error) => {
          console.error('Error loading AudioWorkletProcessor:', error);
        });

        this.audioWorkletNode = new AudioWorkletNode(this.audioContext, 'recorder-processor');
        source.connect(this.audioWorkletNode);

        this.preBufferSize = this.preBufferDuration * this.sampleRate;
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
      }
    },
    storeInPreBuffer(audioData) {
      const dataLength = audioData.length;
      if (dataLength + this.preBufferIndex > this.preBufferSize) {
        const shiftAmount = dataLength + this.preBufferIndex - this.preBufferSize;
        this.preBuffer.copyWithin(0, shiftAmount, this.preBufferIndex);
        this.preBufferIndex -= shiftAmount;
      }
      this.preBuffer.set(audioData, this.preBufferIndex);
      this.preBufferIndex += dataLength;
    },
    clearCanvas() {
      this.canvasCtx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    },
    drawWaveformLine() {
      this.canvasCtx.lineWidth = 2;
      this.canvasCtx.strokeStyle = '#00FFCC';
      this.canvasCtx.beginPath();

      const sliceWidth = this.canvas.width / this.totalSlices;
      let x = 0;
      const centerY = this.canvas.height / 2 - this.verticalOffset;

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
      this.canvasCtx.stroke();
    },
    drawMinMaxLines() {
      const {min: normalizedMinValue, max: normalizedMaxValue} = updateMinMax(
          this.rollingBuffer,
          this.bufferLength,
          this.slicesFor4Seconds,
          this.canvas,
          this.verticalOffset
      );

      this.canvasCtx.strokeStyle = '#f83030';
      this.canvasCtx.lineWidth = 1;
      this.canvasCtx.beginPath();
      this.canvasCtx.moveTo(0, normalizedMaxValue);
      this.canvasCtx.lineTo(this.canvas.width, normalizedMaxValue);
      this.canvasCtx.stroke();

      this.canvasCtx.strokeStyle = '#21219a';
      this.canvasCtx.beginPath();
      this.canvasCtx.moveTo(0, normalizedMinValue);
      this.canvasCtx.lineTo(this.canvas.width, normalizedMinValue);
      this.canvasCtx.stroke();
    },
    drawActivationThresholdLines() {
      const centerY = this.canvas.height / 2 - this.verticalOffset;
      const activationThresholdY = this.canvas.height * (this.thresholdPercentage / 2);

      this.canvasCtx.strokeStyle = '#919b07';
      this.canvasCtx.beginPath();
      this.canvasCtx.moveTo(0, centerY - activationThresholdY);
      this.canvasCtx.lineTo(this.canvas.width, centerY - activationThresholdY);

      this.canvasCtx.moveTo(0, centerY + activationThresholdY);
      this.canvasCtx.lineTo(this.canvas.width, centerY + activationThresholdY);
      this.canvasCtx.stroke();
    },
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

      const preBufferData = this.preBuffer.slice(0, this.preBufferIndex);
      this.recordedSamples.push(...preBufferData);

      this.preBufferIndex = 0;

      this.forceSendTimer = setTimeout(() => {
        this.forceSendChunk('time');
      }, this.forceSendDuration);

      this.recordingTime = 0;

      this.chunkSent = false;
    },
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

      this.delayTimer = setTimeout(() => {
        this.startInactiveTimer();
      }, this.delayDuration);

      this.chunkSent = false;
    },
    resetState() {
      this.isRecording = false;
      this.isActive = false;
      this.reactivationCount = 0;
      this.recordingStartTime = null;
      this.delayStartTime = null;
      this.conditionCounter = 0;
      this.chunkSent = false;

      this.preBufferIndex = 0;
    },
    forceSendChunk(reason) {
      console.log(`Chunk sent due to ${reason}`);

      this.sendChunkToConsole();

      this.resetState();

      if (this.forceSendTimer) {
        clearTimeout(this.forceSendTimer);
        this.forceSendTimer = null;
      }

      this.chunkSent = true;

      this.resetTimer = setTimeout(() => {
        this.chunkSent = false;
      }, this.chunkBeepDuration);

      this.isActive = false;
    },
    async sendChunkToConsole() {
      if (this.recordedSamples.length) {
        try {
          const wavBlob = this.encodeWAV(this.recordedSamples, this.sampleRate);
          console.log('Chunk', this.chunkNumber, 'sent:', wavBlob);

          const formData = new FormData();
          formData.append('file', wavBlob, `chunk_${this.chunkNumber}.wav`);
          console.log('Sending WAV blob:', wavBlob);

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
            if (data.transcription && data.transcription !== 'False activation') {
              this.$emit('transcription-received', data.transcription);
            }
          } else {
            throw new Error('Network response was not ok.');
          }
        } catch (error) {
          console.error('Error sending the chunk:', error);
        } finally {
          this.recordedSamples = [];
          this.chunkNumber++;
        }
      }
    },
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
    updateRollingBuffer() {
      this.analyser.getByteTimeDomainData(this.dataArray);
      this.rollingBuffer.copyWithin(0, this.bufferLength);
      this.rollingBuffer.set(this.dataArray, this.rollingBuffer.length - this.bufferLength);
    },
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
    encodeWAV(samples, sampleRate) {
      const buffer = new ArrayBuffer(44 + samples.length * 2);
      const view = new DataView(buffer);

      this.writeString(view, 0, 'RIFF');
      view.setUint32(4, 36 + samples.length * 2, true);
      this.writeString(view, 8, 'WAVE');
      this.writeString(view, 12, 'fmt ');
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, 1, true);
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate * 2, true);
      view.setUint16(32, 2, true);
      view.setUint16(34, 16, true);
      this.writeString(view, 36, 'data');
      view.setUint32(40, samples.length * 2, true);

      let offset = 44;
      for (let i = 0; i < samples.length; i++, offset += 2) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      }

      return new Blob([view], {type: 'audio/wav'});
    },
    writeString(view, offset, string) {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    },
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
};
</script>
