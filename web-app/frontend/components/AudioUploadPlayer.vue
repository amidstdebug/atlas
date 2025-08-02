<script setup lang="ts">
import { ref, watch } from 'vue'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import AudioSimulationPlayer from './AudioSimulationPlayer.vue'

interface Props {
  isRecording: boolean
  isSimulateMode: boolean
  customWhisperPrompt?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:isSimulateMode': [value: boolean]
}>()

const isSimulating = ref(props.isSimulateMode)

watch(() => props.isSimulateMode, (val) => {
  isSimulating.value = val
})

watch(isSimulating, (val) => {
  emit('update:isSimulateMode', val)
})

</script>

<template>
  <div class="flex items-center space-x-2">
    <Switch 
      id="simulate-mode" 
      :checked="isSimulating" 
      @update:checked="isSimulating = $event" 
      :disabled="props.isRecording" 
    />
    <Label for="simulate-mode">Simulate</Label>
  </div>

  <AudioSimulationPlayer
    v-if="isSimulating"
    @close="isSimulating = false"
    :custom-whisper-prompt="props.customWhisperPrompt"
  />
</template>
