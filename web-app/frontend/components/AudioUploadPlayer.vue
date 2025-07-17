<script setup lang="ts">
import { ref, watch, onBeforeUnmount, nextTick } from 'vue'
import { Play, Pause, Upload, X } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useAudioRecording } from '@/composables/useAudioRecording'
import { Progress } from '@/components/ui/progress'

interface Props {
  open: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:open': [value: boolean]
  'file-transcribed': []
}>()

const isOpen = ref(props.open)
watch(() => props.open, (val) => { isOpen.value = val })
watch(isOpen, (val) => emit('update:open', val))

const fileInput = ref<HTMLInputElement>()
const audioRef = ref<HTMLAudioElement>()
const file = ref<File | null>(null)
const audioUrl = ref('')
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const hasTranscribed = ref(false)
const isTranscribing = ref(false)

function openFileDialog() {
  fileInput.value?.click()
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const f = target.files?.[0]
  if (f) {
    file.value = f
    audioUrl.value = URL.createObjectURL(f)
    // preload duration
    nextTick(() => {
      if (audioRef.value) {
        audioRef.value.load()
      }
    })
  }
}

function togglePlay() {
  if (!file.value || !audioRef.value) return
  if (!hasTranscribed.value) {
    startTranscription()
  }
  if (isPlaying.value) {
    audioRef.value.pause()
  } else {
    audioRef.value.play()
  }
  isPlaying.value = !isPlaying.value
}

function startTranscription() {
  if (!file.value) return
  if (isTranscribing.value) return
  isTranscribing.value = true
  hasTranscribed.value = true
  const { transcribeFile } = useAudioRecording()
  transcribeFile(file.value).finally(() => {
    isTranscribing.value = false
    emit('file-transcribed')
  })
}

function updateTime() {
  if (audioRef.value) {
    currentTime.value = audioRef.value.currentTime
    duration.value = audioRef.value.duration
  }
}

function close() {
  isOpen.value = false
  cleanup()
}

function cleanup() {
  if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
  file.value = null
  audioUrl.value = ''
  isPlaying.value = false
  currentTime.value = 0
  duration.value = 0
  hasTranscribed.value = false
  isTranscribing.value = false
}

onBeforeUnmount(cleanup)
</script>

<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="max-w-md">
      <DialogHeader>
        <DialogTitle>Upload Audio File</DialogTitle>
      </DialogHeader>
      <div class="space-y-4">
        <input ref="fileInput" type="file" accept="audio/*" class="hidden" @change="handleFileChange" />
        <div v-if="!file">
          <Button @click="openFileDialog" class="w-full">
            <Upload class="h-4 w-4 mr-2" />Select Audio File
          </Button>
        </div>
        <div v-else class="space-y-2">
          <p class="text-sm break-all">{{ file.name }}</p>
          <audio ref="audioRef" :src="audioUrl" class="hidden" @timeupdate="updateTime" @ended="isPlaying=false" />
          <div class="flex items-center space-x-3">
            <Button @click="togglePlay" :disabled="isTranscribing" size="icon">
              <Play v-if="!isPlaying" class="h-4 w-4" />
              <Pause v-else class="h-4 w-4" />
            </Button>
            <Progress :model-value="duration ? (currentTime / duration) * 100 : 0" class="flex-1" />
            <span class="text-xs font-mono w-16 text-right">{{ currentTime.toFixed(1) }}s</span>
          </div>
          <div v-if="isTranscribing" class="text-xs text-muted-foreground">Uploading & transcribing...</div>
        </div>
        <div class="flex justify-end">
          <Button variant="ghost" size="sm" @click="close">
            <X class="h-3 w-3 mr-1" />Close
          </Button>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
