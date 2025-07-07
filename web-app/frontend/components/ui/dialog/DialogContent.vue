<script setup lang="ts">
import { cn } from '@/lib/utils'

interface Props {
  class?: string
}

const props = defineProps<Props>()
</script>

<template>
  <div
    :class="cn(
      'bg-background border border-border rounded-lg shadow-lg max-w-lg w-full mx-4 p-6',
      props.class
    )"
  >
    <slot />
  </div>
</template>