<script setup>
const props = defineProps({
  speaker: {
    type: String,
  },
  text: {
    type: String,
  },
  start: {
    type: String,
  },
  end: {
    type: String,
  },
});
</script>

<template>
  <div>
    <div class="flex flex-col items-start justify-center">
      <div v-if="start && end" class="text-stone-400 font-mono text-xs">
        <span>{{ start }}</span
        >-<span>{{ end }}</span>
      </div>
      <div>
        <span class="">{{ speaker }}</span
        >: <span class="text-stone-200">{{ text }}</span>
      </div>
    </div>
  </div>
</template>
