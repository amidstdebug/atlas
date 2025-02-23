<template>
  <el-container>
    <el-main>
      <!-- Row: Transcription (Left) and Summary (Right) -->
      <el-row justify="center" gutter="40" style="margin: 20px 0;">
        <!-- Left Column: Live Transcription (40% width) -->
        <el-col :span="10" class="left-column">
          <el-card class="box-card recording-glow" :class="{ active: isRecording }">
            <template #header>
              <div class="full-header">
                <span style="color:#29353C">{{ leftBoxHeader }}</span>
              </div>
            </template>
            <div class="transcription-box" ref="transcriptionBox">
              <div v-if="transcriptionSegments.length > 0" class="transcription-content">
                <div
                  v-for="(segment, index) in transcriptionSegments"
                  :key="index"
                  class="segment"
                >
                  <span class="speaker-label" :style="getSpeakerStyle(segment.speaker)">
                    Speaker {{ segment.speaker }}:
                  </span>
                  <span class="segment-text">{{ segment.transcription }}</span>
                </div>
              </div>
              <div v-else class="initial-text">
                <p>{{ leftBoxInitial }}</p>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- Right Column: Live Summary (60% width) -->
        <el-col :span="14" class="right-column">
          <el-card class="box-card">
            <template #header>
              <div class="full-header">
                <span style="color:#29353C">{{ rightBoxHeader }}</span>
              </div>
            </template>
            <div class="content-box">
              <el-carousel
                :interval="0"
                arrow="never"
                indicator-position="outside"
                height="600px"
                :loop="false"
                :trigger="'click'"
              >
                <template v-if="summaries.length === 0">
                  <el-carousel-item>
                    <div class="initial-text">
                      <p>{{ rightBoxInitial }}</p>
                    </div>
                  </el-carousel-item>
                </template>
                <template v-else>
                  <el-carousel-item
                    v-for="summary in summaries"
                    :key="summary.id"
                    class="summary-item"
                  >
                    <div class="summary-content" ref="summaryContent">
                      <el-tag type="info" size="small" class="timestamp-tag">
                        {{ summary.timestamp }}
                      </el-tag>
                      <div
                        v-html="summary.formattedContent"
                        class="formatted-summary"
                      ></div>
                    </div>
                  </el-carousel-item>
                </template>
              </el-carousel>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- Merged Button Group -->
      <div class="button-group merged">
        <!-- File Upload Button -->
        <el-button
          :disabled="isTranscribing"
          :style="{ color: uploadColor }"
          class="centered-button same-width-button"
          @click="uploadRecording"
        >
          <el-icon class="icon-group">
            <UploadIcon />
          </el-icon>
          {{ isTranscribing ? 'Transcribing...' : 'Upload Recording' }}
        </el-button>

        <!-- Live Recording (Mic) Button -->
        <el-button
          v-if="!isRecording"
          :style="{ color: liveRecordColor }"
          class="centered-button same-width-button"
          @click="startMicRecording"
        >
          <el-icon class="icon-group">
            <MicrophoneIcon />
          </el-icon>
          Start Recording
        </el-button>
        <el-button
          v-if="isRecording"
          class="centered-button same-width-button"
          @click="stopMicRecording"
        >
          Stop Recording
        </el-button>

        <!-- Clear Transcript Button -->
        <el-button
          class="centered-button same-width-button"
          @click="clearTranscription"
        >
          {{ isTranscribing ? 'Stop Transcribing' : 'Clear Transcript' }}
        </el-button>
      </div>

      <!-- Hidden File Input for Upload -->
      <input
        ref="audioFileInput"
        type="file"
        accept="audio/*"
        style="display: none;"
        @change="handleFileUpload"
      />
    </el-main>
  </el-container>
</template>

<script>
import {
  ElContainer,
  ElMain,
  ElRow,
  ElCol,
  ElCard,
  ElButton,
  ElIcon,
  ElTag,
  ElCarousel,
  ElCarouselItem
} from 'element-plus';
import { Microphone, Upload } from '@element-plus/icons-vue';
import Prism from 'prismjs';
import 'prismjs/themes/prism.css';
import { typeWriterMultiple } from '@/methods/utils/typeWriter';
import { tabConfigurations } from '@/config/columnConfig';
// Removed axios import since HTTP sending is no longer used.
import { AudioRecorderService } from '@/services/audioRecorderService';
import {jsonrepair} from "jsonrepair";

const typingMappings = [
  { configPath: ['headers', 'leftBoxHeader'], dataKey: 'leftBoxHeader' },
  { configPath: ['headers', 'rightBoxHeader'], dataKey: 'rightBoxHeader' },
  { configPath: ['initials', 'leftBoxInitial'], dataKey: 'leftBoxInitial' },
  { configPath: ['initials', 'rightBoxInitial'], dataKey: 'rightBoxInitial' },
];

function getNestedProperty(obj, path) {
  return path.reduce((accumulator, key) => {
    return accumulator && accumulator[key] ? accumulator[key] : undefined;
  }, obj);
}

export default {
  name: 'ColumnLayout',
  components: {
    MicrophoneIcon: Microphone,
    UploadIcon: Upload,
    ElContainer,
    ElMain,
    ElRow,
    ElCol,
    ElCard,
    ElButton,
    ElIcon,
    ElTag,
    ElCarousel,
    ElCarouselItem,
  },
  props: {
    liveRecordColor: {
      type: String,
      default: '#e34660',
    },
    uploadColor: {
      type: String,
      default: '#5773d9',
    },
    transcription: {
      type: [Object, String],
      default: '',
    },
    activeTab: {
      type: String,
    },
  },
  data() {
    return {
      summaries: [],
      leftBoxHeader: "Live Transcription",
      leftBoxInitial: "This is where the live transcriptions will appear...",
      rightBoxHeader: "Live Summary",
      rightBoxInitial: "This is where the live summary will appear...",
      typingSpeed: 11,
      cancelTypingFunctions: [],
      isTranscribing: false,
      // Removed cancelTokenSource and file upload related properties.
      recordedSamples: [],
      sampleRate: 48000,
      chunkSize: 1600000,
      lastSent: false,
      isRecording: false,
      audioRecorder: null,
    };
  },
  computed: {
    transcriptionSegments() {
      if (
        this.transcription &&
        typeof this.transcription === 'object' &&
        Array.isArray(this.transcription.segments)
      ) {
        return this.transcription.segments;
      }
      if (typeof this.transcription === 'string') {
        try {
          const parsed = JSON.parse(this.transcription);
          if (parsed && Array.isArray(parsed.segments)) {
            return parsed.segments;
          }
        } catch (e) {
          return [];
        }
      }
      return [];
    },
    aggregatedTranscription() {
      return this.transcriptionSegments.map(segment => segment.transcription).join("\n");
    },
  },
  methods: {
    handleActiveTabChange(newTab) {
      this.cancelTypingFunctions.forEach(cancelFn => cancelFn());
      this.cancelTypingFunctions = [];
      const config = tabConfigurations[newTab];
      if (config) {
        const typingTasks = typingMappings.map(mapping => {
          const text = getNestedProperty(config, mapping.configPath);
          const dataKey = mapping.dataKey;
          this[dataKey] = '';
          return {
            text: text,
            typingSpeed: this.typingSpeed,
            onUpdate: (currentText) => {
              this[dataKey] = currentText;
            },
            onComplete: () => {},
          };
        });
        this.cancelTypingFunctions = typeWriterMultiple(typingTasks);
      } else {
        console.warn(`No configuration found for activeTab: ${newTab}`);
      }
    },
    // File upload methods updated to use the AudioRecorderService function.
    uploadRecording() {
      this.$refs.audioFileInput.click();
    },
    async handleFileUpload(event) {
      const file = event.target.files[0];
      if (file) {
        if (!this.audioRecorder) {
          this.audioRecorder = new AudioRecorderService({ preBufferDuration: 0.4 });
          // Update the URL accordingly.
          this.audioRecorder.connectWebSocket('ws://your-websocket-server-url');
        }
        const arrayBuffer = await file.arrayBuffer();
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
        // Use the first channel's float32 samples.
        const float32Array = audioBuffer.getChannelData(0);
        // Set the recordedSamples property so that sendRecordedAudio() will send this data.
        this.audioRecorder.recordedSamples = Array.from(float32Array);
        await this.audioRecorder.sendRecordedAudio();
        console.log('File upload payload sent via WebSocket.');
      }
    },
    clearTranscription() {
      this.$emit('transcription-cleared');
      this.summaries = [];
      this.$refs.audioFileInput.value = '';
      this.isTranscribing = false;
    },
    // Microphone recording methods:
    async startMicRecording() {
      if (!this.audioRecorder) {
        this.audioRecorder = new AudioRecorderService({ preBufferDuration: 0.4 });
        // Update the URL accordingly.
        this.audioRecorder.connectWebSocket('ws://your-websocket-server-url');
      }
      await this.audioRecorder.startRecording();
      this.isRecording = true;
    },
    async stopMicRecording() {
      await this.audioRecorder.stopRecording();
      if (this.audioRecorder.audioStream) {
        this.audioRecorder.audioStream.getTracks().forEach(track => track.stop());
      }
      this.isRecording = false;
    },
    getSpeakerStyle(speaker) {
      const colors = {
        "0": "#1f8ef1",
        "1": "#e14eca",
      };
      return {
        backgroundColor: colors[speaker] || "#777",
        color: "white",
        padding: "2px 6px",
        borderRadius: "4px",
        marginRight: "8px",
      };
    },
    addTranscription(newText) {
      this.$emit('transcription-received', newText);
    },
    encodeWAV(samples, sampleRate) {
      return window.encodeWAV(samples, sampleRate);
    },
    convertCamelCase(text) {
      return text.replace(/([A-Z])/g, ' $1').replace(/_/g, ' ').trim();
    },
    capitalizeFirstLetter(text) {
      if (!text) return '';
      return text.charAt(0).toUpperCase() + text.slice(1);
    },
    formatSummary(summaryObj) {
      try {
        let htmlContent = '';
        Object.entries(summaryObj).forEach(([key, value]) => {
          const formattedKey = this.capitalizeFirstLetter(this.convertCamelCase(key));
          if (typeof value === 'object' && !Array.isArray(value)) {
            htmlContent += `<h3>${formattedKey}</h3>`;
            htmlContent += this.formatSummary(value);
          } else if (Array.isArray(value)) {
            if (value.length > 0 && typeof value[0] === 'object') {
              htmlContent += `<h3>${formattedKey}</h3>`;
              value.forEach((item) => {
                htmlContent += `<div class="nested-object">`;
                htmlContent += this.formatSummary(item);
                htmlContent += `</div>`;
              });
            } else {
              htmlContent += `<h3>${formattedKey}</h3>`;
              htmlContent += '<ul>';
              value.forEach((item) => {
                htmlContent += `<li>${item}</li>`;
              });
              htmlContent += '</ul>';
            }
          } else {
            htmlContent += `<p><strong>${formattedKey}:</strong> ${value}</p>`;
          }
        });
        return htmlContent;
      } catch (error) {
        console.error('Error formatting summary:', error);
        return 'Invalid summary format.';
      }
    },
    extractSummary(apiResponse) {
      try {
        const start = apiResponse.indexOf('```');
        if (start === -1) return null;
        const end = apiResponse.indexOf('```', start + 3);
        if (end === -1) return null;
        let extractedContent = apiResponse.substring(start + 3, end).trim();
        extractedContent = extractedContent
          .replace(/\\n/g, '')
          .replace(/\\\\/g, '\\')
          .replace(/\\"/g, '"');
        let repaired = jsonrepair(extractedContent);
        let jsonObj = JSON.parse(repaired);
        return jsonObj;
      } catch (error) {
        console.error('Error extracting and parsing summary:', error);
        return null;
      }
    },
    addSummary(summaryObj) {
      const timestamp = new Date().toLocaleString();
      const formattedContent = this.formatSummary(summaryObj);
      const uniqueId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      this.summaries.unshift({
        id: uniqueId,
        timestamp,
        formattedContent,
        rawContent: summaryObj
      });
      if (this.summaries.length > 10) {
        this.summaries.pop();
      }
    },
  },
  watch: {
    transcription(newVal) {
      // Additional logic for transcription updates.
    },
    activeTab(newTab) {
      this.handleActiveTabChange(newTab);
    },
  },
  mounted() {
    this.$watch(
      () => this.summaries,
      () => {
        this.$nextTick(() => {
          Prism.highlightAll();
        });
      }
    );
    if (this.activeTab) {
      this.handleActiveTabChange(this.activeTab);
    }
  },
  beforeUnmount() {
    this.cancelTypingFunctions.forEach((cancelFn) => cancelFn());
  },
};

/*
Helper function to convert an ArrayBuffer to a base64 string.
This helper could also be imported from a shared utilities file.
*/
function arrayBufferToBase64(buffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}
</script>

<style scoped>
*,
*::before,
*::after {
  box-sizing: border-box;
}

.el-container {
  overflow-x: hidden;
}

.left-column,
.right-column {
  padding: 0 10px;
}

.full-header {
  width: 100%;
  margin: 0;
  padding: 0;
}

.transcription-box,
.content-box {
  position: relative;
  min-height: 600px;
  max-height: 600px;
  background-color: #f9f9f9;
  border-radius: 4px;
  overflow-y: auto;
  border: 4px solid transparent;
  transition: border 0.3s ease-in-out;
}

.recording-glow {
  transition: box-shadow 0.3s ease;
}
.recording-glow.active {
  box-shadow: 0 0 20px 7px rgba(227,70,96,0.7);
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 10px 3px rgba(227,70,96,0.7);
  }
  50% {
    box-shadow: 0 0 20px 7px rgba(227,70,96,0.5);
  }
  100% {
    box-shadow: 0 0 10px 3px rgba(227,70,96,0.7);
  }
}

.transcription-content {
  padding: 20px 20px 20px 30px;
  color: #29353c !important;
}

.initial-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #999;
  padding: 20px;
}

.button-group.merged {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-top: 20px;
}

.icon-group {
  margin-right: 10px;
}

.centered-button {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px;
  min-width: 180px;
  max-width: 180px;
}

.el-carousel {
  width: 100%;
}

.el-carousel .el-carousel__item {
  width: 100%;
}

.el-carousel__indicators {
  bottom: 10px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.summary-content {
  width: 100%;
  padding: 10px 20px;
  overflow-y: auto;
}

.timestamp-tag {
  margin-bottom: 10px;
}

.formatted-summary {
  font-family: 'Arial', sans-serif;
  line-height: 1.6;
  color: #29353c !important;
}

.nested-object {
  border-left: 2px solid #e0e0e0;
  padding-left: 10px;
  margin-bottom: 10px;
}

.el-col {
  padding: 0;
}

.el-row {
  margin: 0;
}

.el-button[disabled] {
  cursor: not-allowed;
  opacity: 0.6;
}
</style>