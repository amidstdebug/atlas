<template>
  <div
    ref="containerRef"
    class="flex flex-col overflow-y-auto gap-2"
    @scroll="handleScroll"
  >
    <TranscriptSpeaker
      v-for="(segment, index) in segments"
      :key="`${segment.speaker}-${index}`"
      :speaker="segment.speaker"
      :text="segment.text"
      :start="segment.startFormatted"
      :end="segment.endFormatted"
    />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from "vue";

const props = defineProps({
  segments: {
    type: Array,
    default: () => [],
  },
});

const containerRef = ref(null);
const shouldAutoScroll = ref(true);

const isAtBottom = () => {
  const container = containerRef.value;
  if (!container) return false;

  // Check if we're within 10px of the bottom to account for small rounding differences
  const threshold = 10;
  return (
    container.scrollHeight - container.scrollTop - container.clientHeight <=
    threshold
  );
};

const scrollToBottom = () => {
  if (!containerRef.value) return;

  containerRef.value.scrollTop = containerRef.value.scrollHeight;
};

const handleScroll = () => {
  shouldAutoScroll.value = isAtBottom();
};

// Watch for changes in segments
watch(
  () => props.segments.length,
  async () => {
    if (shouldAutoScroll.value) {
      // Wait for the DOM to update before scrolling
      await nextTick();
      scrollToBottom();
    }
  },
);

// Initial scroll to bottom when mounted
onMounted(async () => {
  await nextTick();
  scrollToBottom();
});
</script>
