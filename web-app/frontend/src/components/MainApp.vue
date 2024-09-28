<template class="main-app">
  <div>
    <el-row justify="center" gutter="40" style="background:#44576D; margin: 0">
      <el-header height="100px">
        <div class="header-content" style="margin-top:35px">
          <h1 style="color:#e6e6e6">ATLAS - Automated Transmission Language Analysis System</h1>
        </div>
      </el-header>
    </el-row>

    <el-row justify="center" gutter="40">
      <!-- Canvas Layout Column -->
      <el-col :span="7" :offset="1">
        <div class="canvas-container">
          <!-- Listen for transcription-received event -->
          <CanvasLayout
              ref="canvasLayout"
              @transcription-received="updateTranscription"
          />
        </div>
      </el-col>

      <!-- Transcription and Summary Column -->
      <el-col :span="16">
        <ColumnLayout
            :liveRecordColor="liveRecordColor"
            :uploadColor="uploadColor"
            :transcription="transcription"
            @transcription-cleared="clearTranscription"
        />
      </el-col>
    </el-row>
  </div>
</template>

<script>
import ColumnLayout from './ColumnLayout.vue';
import CanvasLayout from './CanvasLayout.vue';

export default {
  name: 'MainApp',
  components: {
    ColumnLayout,
    CanvasLayout,
  },
  mounted() {
    // Change the title of the tab when the component is mounted
    document.title = 'ATLAS';
  },
  data() {
    return {
      liveRecordColor: '#e34660',
      uploadColor: '#5773d9',
      transcription: '', // Store the transcription data
    };
  },
  methods: {
    // Update the transcription data when the event is received
    updateTranscription(transcriptionData) {
      this.transcription += transcriptionData + '\n\n';
    },
    clearTranscription() {
      // Reset the transcription when it is cleared
      this.transcription = '';
    },
  },
};
</script>

<style scoped>
@import '../styles/main.css';

html, body {
  max-width: 100%;
  overflow-x: hidden;
}

#app {
  margin-top: 20px;
  padding: 20px;
}

.main-app {
  color: #29353C;
  width: 100%;
  overflow-x: hidden;
}

.canvas-container {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
}

</style>