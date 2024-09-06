<template>
  <el-container>
    <el-main>
      <!-- Top Column: Live Transcription -->
      <el-row justify="center" gutter="40" style="margin-bottom: 20px;">
        <el-col :span="24" class="top-column">
          <el-card class="box-card">
            <template #header>
              <span>Live Transcription</span>
            </template>
            <div class="content-box transcription-box">
              <!-- Display live transcription -->
              <p v-if="transcription" v-html="transcription.replace(/\n/g, '<br>')"></p>
              <p v-else>This is where the live transcriptions will appear...</p>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- Bottom Column: Live Summary -->
      <el-row justify="center" gutter="40" style="margin-top: 20px;">
        <el-col :span="24" class="bottom-column">
          <el-card class="box-card">
            <template #header>
              <span>Live Summary</span>
            </template>
            <div class="content-box ">
              <slot name="right-content">This is where the live summary will appear...</slot>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <div class="button-group">
        <!-- Live Record Button -->
        <el-button :style="{ color: liveRecordColor }" class="centered-button same-width-button">
          <el-icon class="icon-group">
            <MicrophoneIcon/>
          </el-icon>
          Live Record
        </el-button>

        <!-- Upload Recording Button -->
        <el-button :style="{ color: uploadColor }" class="centered-button same-width-button">
          <el-icon class="icon-group">
            <UploadIcon/>
          </el-icon>
          Upload Recording
        </el-button>

        <!-- Clear Transcript Button -->
        <el-button class="centered-button same-width-button" @click="clearTranscription">
          Clear Transcript
        </el-button>
      </div>
    </el-main>
  </el-container>
</template>

<script>
import {Microphone, Upload} from '@element-plus/icons-vue';

export default {
  name: 'ColumnLayout',
  components: {
    MicrophoneIcon: Microphone,
    UploadIcon: Upload,
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
      default: '', // Empty string by default, will be replaced by real transcription data
    },
  },
  methods: {
    clearTranscription() {
      // Clear the transcription by emitting an event or directly updating the prop
      this.$emit('transcription-cleared');
    },
  },
};
</script>

<style scoped>
/* Add to your existing scoped styles */
.el-container {
  overflow-x: hidden; /* Prevent horizontal scrolling */
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: white;
  background-color: #5369c3;
  padding: 0 20px;
}

.header-content h1 {
  margin: 0;
  font-size: 24px;
}

.canvas-container {
  display: flex;
  justify-content: center;
  align-items: center;
}

.top-column,
.bottom-column {
  display: flex;
  flex-direction: column;
}

.box-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  height: auto;
}

.content-box {
  padding: 20px;
  margin-top: 10px;
  background-color: #f9f9f9;
  border-radius: 4px;
  overflow-y: auto;
}
.transcription-box {
  max-height: 300px; /* Set a maximum height */
  overflow-y: auto; /* Enable scrolling */
}

.button-group {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 10px;
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

.el-col {
  padding: 0 15px;
}

.box-card {
  min-height: 200px;
  max-height: 350px;
}

.el-row {
  margin-left: 20px;
  margin-right: 20px;
}
</style>
