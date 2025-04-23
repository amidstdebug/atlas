<template class="main-app">
  <div>
    <!-- Header Row -->
    <el-row :gutter="40" :style="{ backgroundColor: headerColor, margin: '0', padding: '0' }" class="header-transition">
      <el-header height="100px" style="display: flex; align-items: center;">
        <!-- Logo Section -->
        <div style="flex: 1; display: flex; justify-content: flex-start; align-items: center;">
          <img :src="logo" alt="Logo" class="logo-transition" style="height: 82px; margin-left: 40px;">
        </div>

        <!-- Tabs Centered in Header -->
        <div style="flex: 6; display: flex; justify-content: center; margin-left: 100px;">
          <el-tabs v-model="activeTab" class="header-tabs" @tab-click="handleTabClick" style="width: fit-content;">
            <el-tab-pane label="Automated Air Incident Investigation" name="atc"></el-tab-pane>
            <el-tab-pane label="Automated Meeting Minutes" name="minutes"></el-tab-pane>
          </el-tabs>
        </div>
      </el-header>
    </el-row>

    <!-- Main Content: Only the Transcription & Summary -->
    <el-row justify="center" gutter="40">
      <el-col :span="24">
        <ColumnLayout
          :activeTab="activeTab"
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
import AtlasLight from '../assets/ATLAS_light.png';
import AtlasDark from '../assets/ATLAS_dark.png';

export default {
  name: 'MainApp',
  components: {
    ColumnLayout,
  },
  data() {
    return {
      activeTab: 'atc', // Default active tab
      liveRecordColor: '#e34660',
      uploadColor: '#5773d9',
      transcription: '', // This can be updated via events from ColumnLayout
      headerColor: '#44576D', // Default header color for 'atc'
    };
  },
  computed: {
    // Dynamically set the logo based on the active tab with a fade transition.
    logo() {
      return this.activeTab === 'atc' ? AtlasLight : AtlasDark;
    },
  },
  methods: {
    mapTabIndexToName(index) {
      const tabNames = ['atc', 'minutes'];
      return tabNames[index] || '';
    },

    handleTabClick(tab) {
      console.log('Tab index:', tab.index);
      const tabName = this.mapTabIndexToName(tab.index);
      this.activeTab = tabName;

      // Update header color and other settings based on the active tab.
      if (tabName === 'atc') {
        this.headerColor = '#44576D';
        document.documentElement.style.setProperty('--el-color-primary', '#dfebf6');
        document.documentElement.style.setProperty('--el-color-secondary', '#768a96');
        document.documentElement.style.setProperty('--el-text-color-primary', '#29353c');
      } else if (tabName === 'minutes') {
        this.headerColor = '#8ba4b3';
        document.documentElement.style.setProperty('--el-color-primary', '#28343b');
        document.documentElement.style.setProperty('--el-color-secondary', '#557488');
        document.documentElement.style.setProperty('--el-text-color-primary', '#e4e7ed');
      }

      console.log('Tab clicked:', tabName, 'Active Tab:', this.activeTab, 'Header color:', this.headerColor);
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
.header-transition {
  transition: background-color 0.5s ease-in-out;
}
.logo-transition {
  transition: opacity 1s ease-in-out;
  opacity: 1;
}
.logo-transition:before {
  opacity: 0;
  content: '';
}
.header-tabs > .el-tabs__item.is-active {
  color: #fff !important;
  background-color: transparent !important;
  border-bottom: 2px solid #fff !important;
  font-size: 20px !important;
}
.el-tabs__content {
  display: none;
}
.header-content h1 {
  margin: 0;
}
</style>
