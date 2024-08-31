<template>
  <el-container>
    <el-main>
      <el-row justify="center" gutter="40" style="margin: 40px 0;">
        <!-- Left Column -->
        <el-col :span="10" class="left-column">
          <el-card class="box-card">
            <template #header>
              <span>Live Transcription</span>
            </template>
            <div class="content-box">
              <slot name="left-content">This is where the live transcriptions will appear...</slot>
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
            <template #header>
              <span>Live Summary</span>
            </template>
            <div class="content-box">
              <slot name="right-content">This is where the live summary will appear...</slot>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-main>
  </el-container>
</template>

<script>
import { Microphone, Upload } from '@element-plus/icons-vue';

export default {
  name: 'ColumnLayout',
  components: {
    MicrophoneIcon: Microphone,
    UploadIcon: Upload,
  },
  props: {
    liveRecordColor: {
      type: String,
      default: '#e34660'
    },
    uploadColor: {
      type: String,
      default: '#5773d9'
    }
  }
};
</script>

<style scoped>
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

.left-column, .right-column {
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
