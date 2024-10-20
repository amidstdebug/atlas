<template class="main-app">
  <div>
    <!-- Apply dynamic style binding to the header row -->
    <el-row :gutter="40" :style="{ backgroundColor: headerColor, margin: '0', padding: '0' }" class="header-transition">
      <el-header height="100px" style="display: flex; align-items: center;">
        <!-- Logo Section -->
        <div style="flex: 1; display: flex; justify-content: flex-start; align-items: center;">
          <!-- Bind the logo dynamically based on the active tab and add a fade transition -->
          <img :src="logo" alt="Logo" class="logo-transition" style="height: 82px; margin-left: 40px;">
        </div>

        <!-- Tabs centered in the header -->
        <div style="flex: 6; display: flex; justify-content: center; margin-left: 100px;">
          <!-- Ensure v-model is correctly bound -->
          <el-tabs v-model="activeTab" class="header-tabs" @tab-click="handleTabClick" style="width: fit-content; ">
            <el-tab-pane  label="Automated Air Incident Investigation" name="incident"></el-tab-pane>
            <el-tab-pane label="Automated Meeting Minutes" name="minutes"></el-tab-pane>
          </el-tabs>
        </div>
      </el-header>
    </el-row>

    <el-row justify="center" gutter="40">
      <!-- Canvas Layout Column -->
      <el-col :span="7" :offset="1">
        <div class="canvas-container">
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
      activeTab: 'incident', // Default active tab
      liveRecordColor: '#e34660',
      uploadColor: '#5773d9',
      transcription: '', // Store the transcription data
      headerColor: '#44576D', // Default color for air incident
    };
  },
  computed: {
    // Dynamically set the logo based on the active tab with a transition effect
    logo() {
      return this.activeTab === 'incident'
        ? require('../assets/ATLAS_light.png')
        : require('../assets/ATLAS_dark.png');
    },
  },
  methods: {
    mapTabIndexToName(index) {
      const tabNames = ['incident', 'minutes']; // Add more tab names if needed
      return tabNames[index] || ''; // Return an empty string if the index is out of bounds
    },

    handleTabClick(tab) {
      console.log('Tab index:', tab.index); // Log the tab index

      // Map the tab index to the corresponding tab name
      const tabName = this.mapTabIndexToName(tab.index);
      
      this.activeTab = tabName; // Set the active tab based on the mapped tab name

      // Update header color and other settings based on the active tab
      if (tabName === 'incident') {
        this.headerColor = '#44576D'; // Dark color for incident
        document.documentElement.style.setProperty('--el-color-primary', '#dfebf6'); // primary text color for incident
        document.documentElement.style.setProperty('--el-color-secondary', '#768a96'); // Secondary color for incident
        document.documentElement.style.setProperty('--el-text-color-primary', '#29353c'); // text color for inactive

      } else if (tabName === 'minutes') {
        this.headerColor = '#8ba4b3'; // Light color for meeting minutes
        document.documentElement.style.setProperty('--el-color-primary', '#28343b'); // primary text color for incident
        document.documentElement.style.setProperty('--el-color-secondary', '#557488'); // Secondary color for minutes
        document.documentElement.style.setProperty('--el-text-color-primary', '#e4e7ed'); // text color for inactive
      }

      console.log('Tab clicked:', tabName, 'Active Tab:', this.activeTab, 'Header color:', this.headerColor);
    },

    updateTranscription(transcriptionData) {
      this.transcription += transcriptionData + '\n\n';
    },
    clearTranscription() {
      this.transcription = '';
    },
  },
  mounted() {
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

/* Add smooth transition effect to the background color */
.header-transition {
  transition: background-color 0.5s ease-in-out;
}

/* Add smooth transition effect to the logo */
.logo-transition {
  transition: opacity 1s ease-in-out;
  opacity: 1;
}

.logo-transition:before {
  opacity: 0;
  content: '';
}

/* Optional: Smooth tab active bar transition */
.header-tabs > .el-tabs__item.is-active {
  color: #fff !important; /* Force white color for the active tab */
  background-color: transparent !important; /* Ensure no background color change */
  border-bottom: 2px solid #fff !important; /* Optional: add a bottom border if desired */
  font-size:20px !important;
}

.el-tabs__content {
  display: none; /* Hide tab content completely */
}

.header-content h1 {
  margin: 0;
}

</style>
