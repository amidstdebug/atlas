<template>
  <!-- Fill the parent’s height, hide overflow outside the box -->
  <div class="h-full w-full flex flex-col overflow-hidden">

    <!--
      Scrollable text area region:
      flex-1 => grows to fill vertical space
      overflow-auto => scroll if content is too large
    -->
    <div
      ref="summaryContainer"
      class="flex-1 flex flex-col"
      style="
        background-color: #ffffff;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 16px;
        overflow-y: auto;
      "
    >
      <div v-if="updatingSummary" class="mb-2 text-sm text-gray-500">
        Waiting for summary update...
      </div>
      <Textarea
        v-model="localSummary"
        rows="10"
        class="w-full flex-1 p-2 border rounded resize-none"
      />
    </div>

    <!-- "Apply Changes" button, centered horizontally -->
    <div class="mt-4 flex justify-center">
      <Button
        class="bg-pastel-blue text-white px-4 py-2 rounded disabled:opacity-50"
        :disabled="updatingSummary"
        @click="apply"
      >
        Apply Changes
      </Button>
    </div>
  </div>
</template>

<script>
import {Textarea} from '@/components/ui/textarea'
import {Button} from '@/components/ui/button'

export default {
  name: "SummaryBox",
  components: { Textarea, Button },
  props: {
    summary: {
      type: String,
      default: ''
    },
    updatingSummary: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      localSummary: this.summary
    }
  },
  watch: {
    summary(newVal) {
      this.localSummary = newVal
    }
  },
  methods: {
    apply() {
      this.$emit('apply-changes', this.localSummary)
    }
  },
  updated() {
    // Auto-scroll to the bottom each time the summary updates.
    // Remove if you prefer to avoid jumping while editing.
    const container = this.$refs.summaryContainer
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  }
}
</script>

<style scoped>
</style>