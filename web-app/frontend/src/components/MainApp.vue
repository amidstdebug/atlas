<template class="main-app">
  <div>
    <el-row gutter="40" style="background:#44576D; margin: 0; padding: 0">
      <el-header height="100px" style="display: flex; align-items: center;">
        <!-- Logo Section -->
        <div style="flex: 1; display: flex; justify-content: flex-start; align-items: center;">
          <img src="../assets/ATLAS_light.png" alt="Logo" style="height: 82px; margin-left: 40px;">
        </div>

        <!-- Tabs centered in the header -->
        <div style="flex: 6; display: flex; justify-content: center; margin-left:100px;">
          <el-tabs v-model="activeTab" class="header-tabs" @tab-click="handleClick" style="width: fit-content;">
            <el-tab-pane label="Automated Air Incident Investigation" name="incident"></el-tab-pane>
            <el-tab-pane label="Automated Meeting Minutes" name="minutes"></el-tab-pane>
          </el-tabs>
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
  data() {
    return {
      activeTab: 'incident', // Default active tab is Automated Air Incident Investigation
      liveRecordColor: '#e34660',
      uploadColor: '#5773d9',
      transcription: '', // Store the transcription data
    };
  },
  methods: {
    handleClick(tab, event) {
      console.log(tab, event);
    },
    // Update the transcription data when the event is received
    updateTranscription(transcriptionData) {
      this.transcription += transcriptionData + '\n\n';
    },
    clearTranscription() {
      // Reset the transcription when it is cleared
      this.transcription = '';
    },
  },
  mounted() {
    // Change the title of the tab when the component is mounted
    document.title = 'ATLAS';
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

.header-tabs .el-tabs__header {
  justify-content: center;
  font-size: 16px;
  font-weight: bold;
  color: #e6e6e6; /* Inactive tab color */
  border: none; /* Remove the border under tabs */
}

.el-tabs__item {
  color: #e6e6e6; /* Inactive tab color */
  padding: 0 20px;
}

.header-tabs > .el-tabs__item.is-active {
  color: #fff !important; /* Force white color for the active tab */
  background-color: transparent !important; /* Ensure no background color change */
  border-bottom: 2px solid #fff !important; /* Optional: add a bottom border if desired */
}

.el-tabs__content {
  display: none; /* Hide tab content completely */
}

.header-content h1 {
  margin: 0;
}
</style>
