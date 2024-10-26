<template>
  <el-container>
    <el-main>
      <!-- Row: Transcription and Summary Side by Side -->
      <el-row justify="center" gutter="20" style="margin: 20px 0;">
        <!-- Left Column: Live Transcription -->
        <el-col :span="12" class="left-column">
          <el-card class="box-card">
            <template #header>
              <span style="color:#29353C">{{ leftBoxHeader }}</span>
            </template>
            <div class="transcription-box" ref="transcriptionBox">
              <!-- Display live transcription -->
              <div v-if="transcriptionBuffer" class="transcription-content">
                <p v-html="formattedTranscription"></p>
              </div>
              <div v-else class="initial-text">
                <p>{{ leftBoxInitial }}</p>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- Right Column: Live Summary -->
        <el-col :span="12" class="right-column">
          <el-card class="box-card">
            <template #header>
              <span style="color:#29353C">{{ rightBoxHeader }}</span>
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
                <!-- Initial Carousel Item when no summaries are available -->
                <template v-if="summaries.length === 0">
                  <el-carousel-item>
                    <div class="initial-text">
                      <p>{{ rightBoxInitial }}</p>
                    </div>
                  </el-carousel-item>
                </template>

                <!-- Carousel Items for each summary -->
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

      <!-- Button Group -->
      <div class="button-group">
        <!-- Upload Recording Button -->
        <el-button
            :disabled="isTranscribing"
            :style="{ color: uploadColor }"
            class="centered-button same-width-button"
            @click="uploadRecording"
        >
          <el-icon class="icon-group">
            <UploadIcon/>
          </el-icon>
          {{ isTranscribing ? 'Transcribing...' : 'Upload Recording' }}
        </el-button>

        <!-- Clear Transcript / Stop Transcribing Button -->
        <el-button
            class="centered-button same-width-button"
            @click="clearTranscription"
        >
          {{ isTranscribing ? 'Stop Transcribing' : 'Clear Transcript' }}
        </el-button>
      </div>

      <!-- Hidden File Input -->
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
  ElCarouselItem,
  ElMessage,
} from 'element-plus';
import {Microphone, Upload} from '@element-plus/icons-vue';
import Prism from 'prismjs';
import 'prismjs/themes/prism.css';
import DOMPurify from 'dompurify';
import apiClient from "@/router/apiClient";
import {typeWriterMultiple} from '@/methods/utils/typeWriter'; // Ensure this path is correct
import {tabConfigurations} from '@/config/columnConfig'; // Ensure this path is correct
import axios from 'axios'; // Import axios for cancel tokens
import {jsonrepair} from 'jsonrepair'

// Define typingMappings outside the component for reusability
const typingMappings = [
  {configPath: ['headers', 'leftBoxHeader'], dataKey: 'leftBoxHeader'},
  {configPath: ['headers', 'rightBoxHeader'], dataKey: 'rightBoxHeader'},
  {configPath: ['initials', 'leftBoxInitial'], dataKey: 'leftBoxInitial'},
  {configPath: ['initials', 'rightBoxInitial'], dataKey: 'rightBoxInitial'},
];

/**
 * Retrieves a nested property value from an object based on the provided path.
 *
 * @param {Object} obj - The object to traverse.
 * @param {Array} path - An array representing the path to the desired property.
 * @returns {*} - The value of the nested property or undefined if not found.
 */
function getNestedProperty(obj, path) {
  return path.reduce((accumulator, key) => {
    return accumulator && accumulator[key] ? accumulator[key] : undefined;
  }, obj);
}

export default {
  name: 'ColumnLayout',
  components: {
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
      type: String,
      default: '',
    },
    activeTab: {
      type: String,
    },
  },
  data() {
    return {
      transcriptionBuffer: '', // Used as a buffer for summary, purpose is to reduce token 
      transcriptionDisplay: '', // Displayed on HTML
      summaries: [],
      linesForSummary: 3,
      debouncedGenerateSummary: null,
      transcribeApiEndpoint: '/transcribe',
      audioContext: null,
      lastSent: false,
      audioWorkletNode: null,
      recordedSamples: [],
      sampleRate: 48000,
      chunkSize: 1600000, // Approx. 1 second of audio at 16kHz
      isProcessing: false,
      summaryApiEndpoint: '/summary',
      isTranscribing: false,
      isGeneratingSummary: false,
      cancelTokenSource: null,
      summaryCancelTokenSource: null,
      leftBoxHeader: "Live Transcription",
      leftBoxInitial: "This is where the live transcriptions will appear...",
      rightBoxHeader: "Live Summary",
      rightBoxInitial: "This is where the live summary will appear...",
      typingSpeed: 11, // Speed for typewriter effect
      cancelTypingFunctions: [], // Array to hold cancellation functions
    };
  },
  computed: {
    formattedTranscription() {
      return this.transcriptionDisplay
          ? DOMPurify.sanitize(this.transcriptionDisplay.replace(/\n/g, '<br><br>'))
          : '';
    },
  },
  watch: {
    transcription(newVal, oldVal) {
      if (newVal) {
        let newText = '';
        if (!oldVal) {
          // If there's no old value, consider the entire newVal as new text
          newText = newVal;
        } else if (newVal.length > oldVal.length) {
          // Extract the new text added to the transcription
          newText = newVal.slice(oldVal.length);
        } else {
          // If newVal is shorter or equal, assume transcription was reset
          newText = newVal;
        }

        this.addTranscription(newText.trim());
      }
    },
    activeTab(newTab) {
      this.handleActiveTabChange(newTab);
    },
  },


  methods: {
    /**
     * Handles changes to the activeTab prop.
     * Initiates typewriter effects for headers and initials based on the newTab configuration.
     *
     * @param {String} newTab - The new activeTab value.
     */
    handleActiveTabChange(newTab) {
      // Clear existing typewriter effects
      this.cancelTypingFunctions.forEach(cancelFn => cancelFn());
      this.cancelTypingFunctions = [];

      // Get the configuration for the new tab
      const config = tabConfigurations[newTab];

      if (config) {
        // Define typing tasks dynamically based on the mapping
        const typingTasks = typingMappings.map(mapping => {
          const text = getNestedProperty(config, mapping.configPath);
          const dataKey = mapping.dataKey;

          // Reset the target data property to empty string
          this[dataKey] = '';

          return {
            text: text,
            typingSpeed: this.typingSpeed,
            onUpdate: (currentText) => {
              this[dataKey] = currentText;
            },
            onComplete: () => {
              // Optional: Actions after typing completes for each task
            },
          };
        });

        // Start typewriter effects and store cancellation functions
        this.cancelTypingFunctions = typeWriterMultiple(typingTasks);
      } else {
        console.warn(`No configuration found for activeTab: ${newTab}`);
      }
    },
    /**
     * Open the file selection dialog to upload audio.
     */
    uploadRecording() {
      this.$refs.audioFileInput.click();
    },

    /**
     * Handle the uploaded audio file.
     */
    async handleFileUpload(event) {
      const file = event.target.files[0];
      if (file) {
        // Start transcription process
        this.isTranscribing = true;
        // Create a cancel token source
        this.cancelTokenSource = axios.CancelToken.source();
        await this.processAudioFile(file);
      }
    },

    /**
     * Process the uploaded audio file, chunking and sending it to the backend.
     * @param {File} file - Uploaded audio file.
     */
    async processAudioFile(file) {
      const arrayBuffer = await file.arrayBuffer();
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();

      const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
      this.sampleRate = audioBuffer.sampleRate;

      this.recordedSamples = Array.from(audioBuffer.getChannelData(0)); // Assume mono audio
      await this.chunkAndSendAudio(); // Await to ensure completion

      // After processing, reset transcription state
      this.isTranscribing = false;
      this.cancelTokenSource = null;
    },

    /**
     * Split the audio into chunks and send each chunk to the backend.
     */
    async chunkAndSendAudio() {
      for (let offset = 0; offset < this.recordedSamples.length && this.isTranscribing; offset += this.chunkSize) {
        const chunk = this.recordedSamples.slice(offset, offset + this.chunkSize);

        if (offset + this.chunkSize >= this.recordedSamples.length) {
          this.lastSent = true;
        }
        await this.sendChunk(chunk);
      }
    },

    /**
     * Send the audio chunk to the backend for transcription.
     * @param {Float32Array} chunk - Audio data chunk.
     */
    async sendChunk(chunk) {
      try {
        // Encode the chunk into WAV format
        const wavBlob = this.encodeWAV(chunk, this.sampleRate);

        // Create form data for the request
        const formData = new FormData();
        formData.append('file', wavBlob, 'audio_chunk.wav');

        // Make the POST request
        const response = await apiClient.post(
            this.transcribeApiEndpoint,
            formData,
            {
              headers: {
                'Content-Type': 'multipart/form-data',
              },
              cancelToken: this.cancelTokenSource.token,
            }
        );

        // Handle the backend response
        if (response.status === 200 && response.data.transcription) {
          const transcription = response.data.transcription;
          console.log("reply:", response.data.transcription)
          this.addTranscription(transcription);
        } else {
          console.error('Error in transcription response:', response);
        }
      } catch (error) {
        if (axios.isCancel(error)) {
          console.log('Transcription request canceled:', error.message);
        } else {
          console.error('Error sending audio chunk:', error);
        }
      }
    },

    addTranscription(newText) {
      this.transcriptionDisplay += newText + '\n';

      this.scrollToBottom();

      const lineCount = this.transcriptionDisplay
          .split('\n')
          .filter((line) => line.trim() !== '').length;

      this.transcriptionBuffer = this.transcriptionDisplay.split('\n').filter((word) => word.length != 0).slice(
          -this.linesForSummary
      ).join('\n');

      console.log(this.transcriptionDisplay.split('\n').filter((word) => word.length != 0).slice(-this.linesForSummary))

      if (
          (lineCount >= 3 && this.isTranscribing && lineCount % this.linesForSummary == 0)
          ||
          this.lastSent
      ) {
        console.log("FinaL?", this.lastSent)
        this.generateSummary()
        this.lastSent = false
      }
    },

    clearTranscription() {
      if (this.isTranscribing) {
        // Stop transcribing
        this.isTranscribing = false;

        // Cancel any ongoing transcription requests
        if (this.cancelTokenSource) {
          this.cancelTokenSource.cancel('Transcription stopped by user.');
          this.cancelTokenSource = null;
        }

        // Cancel any ongoing summary generation
        if (this.summaryCancelTokenSource) {
          this.summaryCancelTokenSource.cancel('Summary generation stopped by user.');
          this.summaryCancelTokenSource = null;
        }

        ElMessage.success('Transcription stopped.');
      } else {
        this.transcriptionBuffer = '';
        this.transcriptionDisplay = '';
        this.summaries = [];
        this.$emit('transcription-cleared');
        ElMessage.success('Transcription and summaries cleared.');
      }

      // Reset file input to allow re-uploading
      this.$refs.audioFileInput.value = '';  // Ensures re-selection works

      // Explicitly set `isTranscribing` to false to make sure button is not disabled
      this.isTranscribing = false;
    },


    scrollToBottom() {
      this.$nextTick(() => {
        const box = this.$refs.transcriptionBox;
        if (box) {
          box.scrollTop = box.scrollHeight;
        }
        const box2 = this.$refs.summaryContent;
        if (box2) {
          box2.scrollTop = box2.scrollHeight;
        }
      });
    },
    /**
     * Encode recorded audio samples into WAV format.
     * @param {Float32Array} samples - Recorded audio samples.
     * @param {number} sampleRate - Audio sample rate.
     * @returns {Blob} - WAV audio blob.
     */
    encodeWAV(samples, sampleRate) {
      const buffer = new ArrayBuffer(44 + samples.length * 2); // WAV header + samples
      const view = new DataView(buffer);

      // RIFF chunk descriptor
      this.writeString(view, 0, 'RIFF');
      view.setUint32(4, 36 + samples.length * 2, true); // File size - 8 bytes
      this.writeString(view, 8, 'WAVE');

      // FMT sub-chunk (format of the WAV)
      this.writeString(view, 12, 'fmt ');
      view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
      view.setUint16(20, 1, true); // Audio format (1 = PCM)
      view.setUint16(22, 1, true); // Number of channels (1 = mono)
      view.setUint32(24, sampleRate, true); // Sample rate
      view.setUint32(28, sampleRate * 2, true); // Byte rate (SampleRate * NumChannels * BitsPerSample/8)
      view.setUint16(32, 2, true); // Block align (NumChannels * BitsPerSample/8)
      view.setUint16(34, 16, true); // Bits per sample (16 bits for PCM)

      // Data sub-chunk (actual audio samples)
      this.writeString(view, 36, 'data');
      view.setUint32(40, samples.length * 2, true); // NumSamples * NumChannels * BitsPerSample/8

      // Write the PCM samples
      let offset = 44;
      for (let i = 0; i < samples.length; i++, offset += 2) {
        const s = Math.max(-1, Math.min(1, samples[i])); // Clamp sample values between -1 and 1
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true); // Convert to 16-bit PCM
      }

      return new Blob([view], {type: 'audio/wav'}); // Create the Blob (WAV file)
    },

    /**
     * Helper to write strings into the DataView for WAV header.
     * @param {DataView} view
     * @param {number} offset
     * @param {string} string
     */
    writeString(view, offset, string) {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    },


    async generateSummary() {
      if (!this.isTranscribing) {
        // skips if transcription previous transcription still going on
        return;
      }
      console.log("Generating summary")

      this.isGeneratingSummary = true;
      this.summaryCancelTokenSource = axios.CancelToken.source();

      console.log("Sending:", this.transcriptionBuffer)
      try {
        let payload = {
          transcription: this.transcriptionBuffer.trim(),
          previous_report: null,
          summary_mode: this.activeTab,
        };

        // Include previous_report if available
        if (this.summaries.length > 0) {
          // Get the most recent summary's formatted content as previous_report
          const previousReport = this.summaries[0].rawContent;
          payload.previous_report = previousReport;
        }

        console.log("Sending payload:")
        console.log(payload)

        const response = await apiClient.post(
            this.summaryApiEndpoint,
            payload,
            {
              headers: {
                'Content-Type': 'application/json',
              },
              cancelToken: this.summaryCancelTokenSource.token,
            }
        );

        console.log("Receive")
        console.log(response.data)

        if (
            response.data &&
            response.data.message &&
            response.data.message.content
        ) {
          const apiResponse = response.data.message.content;
          const summaryObj = this.extractSummary(apiResponse);
          console.log("After extract")
          console.log(summaryObj)
          if (summaryObj) {
            this.addSummary(summaryObj);
            ElMessage.success('Summary generated successfully.');
          } else {
            ElMessage.warning('No summary found in the API response.');
          }
        } else {
          ElMessage.warning('Unexpected API response structure.');
        }
      } catch (error) {
        if (axios.isCancel(error)) {
          console.log('Summary generation canceled:', error.message);
        } else {
          console.error('Error generating summary:', error);
          if (error.response) {
            if (error.response.status === 401) {
              ElMessage.error('Unauthorized: Please check your API credentials.');
            } else {
              ElMessage.error(
                  `Error ${error.response.status}: ${error.response.statusText}`
              );
            }
          } else if (error.request) {
            ElMessage.error(
                'No response from the server. Please check your network.'
            );
          } else {
            ElMessage.error(`Request error: ${error.message}`);
          }
        }
      } finally {
        this.isGeneratingSummary = false;
        this.summaryCancelTokenSource = null;
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
        console.log(extractedContent);
        let repaired = jsonrepair(extractedContent)
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

      // Generate a unique ID for each summary
      const uniqueId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

      this.summaries.unshift({
        id: uniqueId, // Add unique ID
        timestamp,
        formattedContent,
        rawContent: summaryObj
      });
      console.log(`Summary added. Total summaries: ${this.summaries.length}`);
      if (this.summaries.length > 10) {
        this.summaries.pop();
        console.log(`Summary removed. Total summaries: ${this.summaries.length}`);
      }
    },
    formatSummary(summaryObj) {
      try {
        let htmlContent = '';

        Object.entries(summaryObj).forEach(([key, value]) => {
          const formattedKey = this.capitalizeFirstLetter(
              this.convertCamelCase(key)
          );

          if (typeof value === 'object' && !Array.isArray(value)) {
            htmlContent += `<h3>${formattedKey}</h3>`;
            htmlContent += this.formatSummary(value);
          } else if (Array.isArray(value)) {
            // Check if the array contains objects
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
      return text
          .replace(/([A-Z])/g, ' $1')
          .replace(/_/g, ' ')
          .trim();
    },
    capitalizeFirstLetter(text) {
      if (!text) return '';
      return text.charAt(0).toUpperCase() + text.slice(1);
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

    // If activeTab is already set when the component mounts, handle it
    if (this.activeTab) {
      this.handleActiveTabChange(this.activeTab);
    }
  },
  beforeUnmount() {
    // Clean up any pending typing effects when the component is destroyed
    this.cancelTypingFunctions.forEach((cancelFn) => cancelFn());

    // Additional cleanup if necessary
  },
};
</script>

<style scoped>
/* Reset box-sizing for all elements */
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

.transcription-box {
  position: relative;
  min-height: 600px;
  max-height: 600px;
  background-color: #f9f9f9;
  border-radius: 4px;
  scroll-behavior: smooth;
  overflow-y: auto;
}

.transcription-content {
  padding: 20px 20px 20px 30px; /* Added left padding */
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

.content-box {
  min-height: 600px;
  max-height: 600px;
  padding: 0;
  background-color: #f9f9f9;
  border-radius: 4px;
  overflow-y: auto;
}

.button-group {
  display: flex;
  justify-content: center;
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
  text-align: center;
  padding: 10px;
  box-sizing: border-box;
}

.same-width-button {
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
  flex: 1;
  overflow-y: auto; /* Enable vertical scrolling */
}

.timestamp-tag {
  margin-bottom: 10px;
}

.formatted-summary {
  width: 100%;
  font-family: 'Arial', sans-serif;
  line-height: 1.6;
  color: #29353c !important;
}

/* Styling for nested objects within summaries */
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

/* Disable the upload button when transcribing */
.el-button[disabled] {
  cursor: not-allowed;
  opacity: 0.6;
}
</style>