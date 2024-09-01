<template>
  <div>
    <el-row justify="center" gutter="40" style="margin: 40px 0;">
      <el-header height="60px">
        <div class="header-content">
          <h1>WaveLink - Automated Transcriptions and Summaries</h1>
        </div>
      </el-header>
    </el-row>

    <el-row justify="center" gutter="40">
      <!-- Left Side: Waveform -->
      <el-col :span="10">
        <div class="canvas-container">
          <CanvasLayout ref="canvasLayout"></CanvasLayout>
        </div>
      </el-col>

      <!-- Right Side: Columns (Stacked) -->
      <el-col :span="10">
        <ColumnLayout :liveRecordColor="liveRecordColor" :uploadColor="uploadColor">
          <template #left-content>
            <p>This is where the live transcriptions will appear...</p>
          </template>
          <template #right-content>
            <p>This is where the live summary will appear...</p>
          </template>
        </ColumnLayout>
      </el-col>
    </el-row>
  </div>
</template>


<script>
import ColumnLayout from './components/ColumnLayout.vue';
import CanvasLayout from './components/CanvasLayout.vue';

export default {
  name: 'App',
  components: {
    ColumnLayout,
    CanvasLayout,
  },
  data() {
    return {
      liveRecordColor: '#e34660',
      uploadColor: '#5773d9',
    };
  },
  mounted() {
    // this.$nextTick(() => {
    //   this.resizeCanvas();
    // });
  },
  methods: {
    // resizeCanvas() {
    //   const baseWidth = 800;  // Smaller canvas width
    //   const baseHeight = 200; // Smaller canvas height
    //
    //   if (this.$refs.canvasLayout && typeof this.$refs.canvasLayout.resizeCanvas === 'function') {
    //     this.$refs.canvasLayout.resizeCanvas(baseWidth, baseHeight);
    //   } else {
    //     console.error('resizeCanvas method not found on CanvasLayout');
    //   }
    // },
  },
};
</script>

<style scoped>
@import './styles/main.css';

#app {
  margin-top: 20px;
  padding: 20px;
}

.canvas-container {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%; /* Ensure it takes up full width */
}
</style>
