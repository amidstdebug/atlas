<template>
  <div>
    <!-- Button to open the dialog -->
    <el-button type="primary" @click="dialogVisible = true">Open Dialog</el-button>

    <!-- Element Plus dialog -->
    <el-dialog
      title="Dialog Title"
      v-model="dialogVisible"
      width="30%"
      :before-close="handleClose"
    >
      <span>This is a dialog box content.</span>
      
      <!-- Dialog footer with buttons -->
      <template #footer>
        <el-button @click="dialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="dialogVisible = false">Confirm</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
export default {
  name: 'ElementTest',
  data() {
    return {
      dialogVisible: false, // Controls the visibility of the dialog
    };
  },
  methods: {
    handleClose(done) {
      this.dialogVisible = false;
      done(); // This method can be customized for additional logic on close
    },
  },
};
</script>