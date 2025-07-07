<script setup lang="ts">
interface Props {
  asChild?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  asChild: false
})

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

function handleClick(event: MouseEvent) {
  emit('click', event)
}
</script>

<template>
  <div v-if="asChild" @click="handleClick">
    <slot />
  </div>
  <button v-else @click="handleClick">
    <slot />
  </button>
</template>