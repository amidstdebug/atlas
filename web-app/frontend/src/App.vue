<template>
  <div id="app">
    <el-container>
      <el-header height="60px">
        <div class="header-content">
          <h1>WaveLink - Automating Transcriptions & FAIR/GAIR</h1>
        </div>
      </el-header>

      <el-main>
        <!-- Main Content -->
        <el-row justify="center" gutter="40" style="margin: 40px 0;">
          <!-- Left Column -->
          <el-col :span="10" class="left-column">
            <el-card class="box-card">
              <div slot="header" class="clearfix">
                <span>Live Transcription</span>
              </div>
              <div class="content-box">
                <!-- Placeholder for live transcription content -->
                <p>This is where the live transcriptions will appear...</p>
              </div>
            </el-card>
            
            <div class="button-group">
              <el-button :color="liveRecordColor" class="centered-button same-width-button">
                <el-icon class="icon-group">
                  <MicrophoneIcon />
                </el-icon>
                Live Record
              </el-button>
          
              <el-button :color="uploadColor" class="centered-button same-width-button">
                <el-icon class="icon-group">
                  <UploadIcon />
                </el-icon>
                Upload Recording
              </el-button>
            </div>
          </el-col>

          <!-- Right Column -->
          <el-col :span="10" class="right-column">
            <el-card class="box-card">
              <div slot="header" class="clearfix">
                <span>Live FAIR / GAIR</span>
              </div>
              <div class="content-box">
                <!-- Placeholder for live GPT call results -->
                <p>This is where the live FAIR / GAIR will appear...</p>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-main>
    </el-container>
  </div>
</template>

<script>
import { Microphone, Upload } from '@element-plus/icons-vue';

export default {
  name: 'App',
  components: {
    MicrophoneIcon: Microphone,
    UploadIcon: Upload,
  },
  data() {
    return {
      liveRecordColor: '#e34660', // Define the color for Live Record button
      uploadColor: '#5773d9',      // Define the color for Upload button
    };
  },
};
</script>

<style scoped>
/* Global App Styles */
@import './styles/main.css';

/* Header Styles */
.header-content {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: white;
  background-color: #5369c3; /* Element Plus primary color */
  padding: 0 20px;
}

.header-content h1 {
  margin: 0;
  font-size: 24px;
}

/* Layout and Column Styles */
#app {
  margin-top: 20px;
  padding: 20px;
}

.el-row {
  justify-content: center;
}

.left-column, .right-column {
  display: flex;
  flex-direction: column;
}

.box-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  height: auto; /* Make the boxes more compact */
}

.transcription-content {
  flex-grow: 1;
  padding: 10px;
  overflow-y: auto;
  background-color: #f9f9f9;
  border-radius: 4px;
  margin-bottom: 10px; /* Less margin for a more compact layout */
}

.content-box {
  padding: 20px; /* Add padding inside the content box */
  margin-top: 10px; /* Add space between the header and content */
  background-color: #f9f9f9; /* Keep the light background color */
  border-radius: 4px; /* Rounded corners for the content box */
  overflow-y: auto; /* Allow for scrolling if the content overflows */
}

.gpt-content {
  padding: 20px; /* Add padding inside the content box */
  margin-top: 10px; /* Add space between the header and content */
  background-color: #f9f9f9; /* Keep the light background color */
  border-radius: 4px; /* Rounded corners for the content box */
  overflow-y: auto; /* Allow for scrolling if the content overflows */
}
.button-group {
  display: flex;
  justify-content: center; /* Center the buttons horizontally */
  gap: 10px; /* Space between the buttons */
  margin-top: 10px;
}

.icon-group {
  margin-right: 10px;
}

/* Ensure the button text and icon are centered */
.centered-button {
  display: flex;               /* Use flexbox to align items */
  align-items: center;         /* Center content vertically */
  justify-content: center;     /* Center content horizontally */
  text-align: center;          /* Ensure text is centered */
  padding: 10px;               /* Add padding for better spacing */
  box-sizing: border-box;      /* Ensure padding doesn't affect width */
}
.box-header {
  margin-bottom:10px;
}

/* Make both buttons the same width */
.same-width-button {
  min-width: 180px;  /* Set a minimum width for buttons */
  max-width: 180px;  /* Ensure buttons have the same maximum width */
}

/* Adjust box sizes and margins */
.el-col {
  padding: 0 15px; /* Increase left-right margin */
}

.box-card {
  min-height: 200px; /* Ensure there's enough space for content */
  max-height: 350px; /* Limit max height to keep it "cute-sized" */
}

.el-row {
  margin-left: 20px; /* Increase overall left margin */
  margin-right: 20px; /* Increase overall right margin */
}
</style>
