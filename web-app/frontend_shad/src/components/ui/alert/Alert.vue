<script setup>
import { cn } from '@/modules/utils';
import { alertVariants } from '.';

const props = defineProps({
  class: { type: null, required: false },
  variant: { type: null, required: false },
});
</script>

<template>
  <div :class="cn(alertVariants({ variant }), props.class)" role="alert">
    <slot />
  </div>
</template>
