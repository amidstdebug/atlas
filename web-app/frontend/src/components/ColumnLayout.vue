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
              <!-- Use parsedSegments to loop over each actual text segment -->
              <div v-if="parsedSegments.length > 0" class="transcription-content">
                <div 
                  v-for="(segment, index) in parsedSegments" 
                  :key="index" 
                  class="segment"
                >
                  <!-- Timestamp -->
                  <span class="segment-timestamp">
                    {{ formatTimestamp(segment.start) }}
                  </span>
                  <!-- Text -->
                  <span class="segment-text">
                    {{ segment.text }}
                  </span>
                </div>
              </div>
              <!-- Otherwise, show placeholder text -->
              <div v-else class="initial-text">
                <p>Upload recording or record audio to transcribe.</p>
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

        <!-- Generate Summary Button -->
        <el-button
          class="centered-button same-width-button"
          @click="generateSummary"
        >
          Generate Summary
        </el-button>

        <!-- Toggle Auto Summary Button -->
        <el-button
          class="centered-button same-width-button"
          @click="toggleAutoSummary"
        >
          {{ autoSummaryEnabled ? 'Disable Auto Summary' : 'Enable Auto Summary' }}
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
import apiClient, { getLoadingStatus } from '@/router/apiClient';
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
  ElCarouselItem,
  ElLoading,
  ElMessage
} from 'element-plus';
import { Microphone, Upload } from '@element-plus/icons-vue';
import Prism from 'prismjs';
import 'prismjs/themes/prism.css';
import { typeWriterMultiple } from '@/methods/utils/typeWriter';
import { tabConfigurations } from '@/config/columnConfig';
import { AudioRecorderService } from '@/services/audioRecorderService';
import { jsonrepair } from 'jsonrepair';
import Cookies from 'js-cookie';

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
      isRecording: false,
      audioRecorder: null,
      liveTranscription: {
        segments: []
      },
      cumulativeOffset: 0, // track audio offset for live recording segments
      apiStatus: getLoadingStatus(),
      // New properties for automatic summary generation
      autoSummaryEnabled: false,
      autoSummaryInterval: null,
      previousSummaryLength: 0  
    };
  },
  computed: {
    /**
     * Returns whichever segments are in “liveTranscription” or “transcription” prop
     */
    transcriptionSegments() {
      if (
        this.liveTranscription &&
        Array.isArray(this.liveTranscription.segments)
      ) {
        return this.liveTranscription.segments;
      }
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

    /**
     * Parses the actual text segments out of the transcription segments.
     */
    parsedSegments() {
      if (!this.transcriptionSegments.length) return [];

      const allSegments = [];
      for (const item of this.transcriptionSegments) {
        if (!item.transcription) continue;
        try {
          const parsed = JSON.parse(item.transcription);
          if (parsed.segments && Array.isArray(parsed.segments)) {
            allSegments.push(...parsed.segments);
          }
        } catch (err) {
          console.error("Could not parse JSON from transcription item:", err);
        }
      }
      return allSegments;
    },

    /**
     * Joins all chunked transcriptions for the “Generate Summary” request.
     */
    aggregatedTranscription() {
      return this.transcriptionSegments
        .map(segment => segment.transcription)
        .join("\n");
    },
  },
  methods: {
    async startMicRecording() {
      if (!this.audioRecorder) {
        this.audioRecorder = new AudioRecorderService({
          apiUrl: "http://localhost:5002" // adjust as needed
        });

        // Handle partial transcripts from the server
        this.audioRecorder.onTranscription = (rawString) => {
          try {
            const parsedData = JSON.parse(rawString);
            let segments = [];

            if (Array.isArray(parsedData)) {
              segments = parsedData;
            } else if (parsedData.segments && Array.isArray(parsedData.segments)) {
              segments = parsedData.segments;
            } else if (parsedData.text) {
              segments = [{
                start: 0,
                end: 1.5,
                text: parsedData.text
              }];
            } else {
              console.error("Invalid transcription format:", parsedData);
              return;
            }

            segments = segments.map(seg => ({
              ...seg,
              start: seg.start + this.cumulativeOffset,
              end: seg.end + this.cumulativeOffset
            }));

            if (segments.length > 0) {
              this.cumulativeOffset = segments[segments.length - 1].end;
            }

            this.liveTranscription.segments.push({
              speaker: 0,
              transcription: JSON.stringify({ segments })
            });
          } catch (error) {
            console.error("Error parsing server transcription chunk:", error);
          }
        };
      }
      this.isRecording = true;
      await this.audioRecorder.startRecording();
    },

    async stopMicRecording() {
      await this.audioRecorder.stopRecording();
      if (this.audioRecorder.audioStream) {
        this.audioRecorder.audioStream.getTracks().forEach(track => track.stop());
      }
      this.isRecording = false;
    },

    formatTimestamp(seconds) {
      if (typeof seconds !== 'number' || isNaN(seconds)) return '';
      const m = Math.floor(seconds / 60);
      const s = Math.floor(seconds % 60);
      return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    },

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
            text,
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

    uploadRecording() {
      this.$refs.audioFileInput.click();
    },

    async handleFileUpload(event) {
      const file = event.target.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append('file', file);

      let loadingInstance;
      try {
        loadingInstance = ElLoading.service({
          fullscreen: true,
          text: 'Uploading and transcribing...'
        });
        
        const response = await apiClient.post('transcribe', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        this.addTranscription(response.data.transcription);
        ElMessage.success('Transcription completed successfully');
      } catch (error) {
        console.error('Error uploading file:', error);
        ElMessage.error('Failed to transcribe file');
      } finally {
        if (loadingInstance) loadingInstance.close();
      }
    },

    addTranscription(newText) {
        // When receiving transcription data (e.g. from a file upload)
        if (newText && newText.segments) {
            // Use the segments from the file upload.
            const segments = newText.segments;
            // Update the cumulative offset from the last segment's end if it is greater.
            if (segments.length > 0) {
            const lastSegment = segments[segments.length - 1];
            if (typeof lastSegment.end === 'number' && lastSegment.end > this.cumulativeOffset) {
                this.cumulativeOffset = lastSegment.end;
            }
            }
            // Append the file transcription as a single chunk (JSON-stringified) into liveTranscription.
            this.liveTranscription.segments.push({
            speaker: 0,
            transcription: JSON.stringify({ segments })
            });
        } else if (typeof newText === 'string') {
            try {
            // Attempt to parse the string
            const parsed = JSON.parse(newText);
            if (parsed.segments && parsed.segments.length > 0) {
                const lastSegment = parsed.segments[parsed.segments.length - 1];
                if (typeof lastSegment.end === 'number' && lastSegment.end > this.cumulativeOffset) {
                this.cumulativeOffset = lastSegment.end;
                }
            }
            this.liveTranscription.segments.push({
                speaker: 0,
                transcription: newText
            });
            } catch (e) {
            // If the string cannot be parsed, just push it as is.
            this.liveTranscription.segments.push({
                speaker: 0,
                transcription: newText
            });
            }
        }
    },

    clearTranscription() {
      this.$emit('transcription-cleared');
      this.summaries = [];
      this.$refs.audioFileInput.value = '';
      this.isTranscribing = false;
      this.liveTranscription.segments = [];
      this.cumulativeOffset = 0;
    },

    async generateSummary() {
      if (!this.aggregatedTranscription.trim()) {
        ElMessage.warning("No transcription to summarize.");
        return;
      }

      let loadingInstance;
      try {
        // loadingInstance = ElLoading.service({
        //   fullscreen: true,
        //   text: 'Generating summary...'
        // });

        const payload = {
          transcription: this.aggregatedTranscription,
          previous_report: "",
          summary_mode: "atc",
        };
        const response = await apiClient.post('summary', payload);
        const apiSummary = response.data.message.content;
        console.log("API:", apiSummary)
        const summaryObj = this.extractSummary(apiSummary);

        if (summaryObj) {
          this.addSummary(summaryObj.meeting_minutes || summaryObj);
          ElMessage.success('Summary generated successfully');
        } else {
          ElMessage.error('Failed to parse summary response');
        }
      } catch (error) {
        console.error('Error generating summary:', error);
        ElMessage.error('Failed to generate summary');
      } finally {
        if (loadingInstance) loadingInstance.close();
      }
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

    extractSummary(apiResponse) {
        try {
            const end = apiResponse.lastIndexOf('```');
            if (end === -1) return null;
            const start = apiResponse.lastIndexOf('```', end - 1);
            if (start === -1) return null;

            let extracted = apiResponse.substring(start + 3, end).trim();
            extracted = extracted
            .replace(/\\n/g, '')
            .replace(/\\\\/g, '\\')
            .replace(/\\"/g, '"');

            const repaired = jsonrepair(extracted);
            return JSON.parse(repaired);
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

    convertCamelCase(text) {
      return text.replace(/([A-Z])/g, ' $1').replace(/_/g, ' ').trim();
    },

    capitalizeFirstLetter(text) {
      if (!text) return '';
      return text.charAt(0).toUpperCase() + text.slice(1);
    },

    // New method to toggle automatic summary generation
    toggleAutoSummary() {
      this.autoSummaryEnabled = !this.autoSummaryEnabled;
      if (this.autoSummaryEnabled) {
        // Start an interval that automatically generates a summary every 15 seconds
        this.autoSummaryInterval = setInterval(() => {
          if (this.aggregatedTranscription.trim().length > 50 && this.aggregatedTranscription.trim().length != this.previousSummaryLength) {
            this.generateSummary();
            this.previousSummaryLength = this.aggregatedTranscription.trim().length
          }
        }, 15000);
      } else {
        clearInterval(this.autoSummaryInterval);
        this.autoSummaryInterval = null;
      }
    },
  },
  watch: {
    transcription(newVal) {
      // handle updates if needed
    },
    activeTab(newTab) {
      this.handleActiveTabChange(newTab);
    },
    'apiStatus.loading'(isLoading) {
      this.isTranscribing = isLoading;
    }
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
    this.cancelTypingFunctions.forEach(cancelFn => cancelFn());
    if (this.autoSummaryInterval) {
      clearInterval(this.autoSummaryInterval);
    }
  },
};
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

/* Each displayed segment */
.segment {
  margin-bottom: 10px;
}

/* Show bold “mm:ss” plus a space before the text */
.segment-timestamp {
  font-weight: bold;
  margin-right: 8px;
}

/* Wrap text within the container for long segments */
.segment-text {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
