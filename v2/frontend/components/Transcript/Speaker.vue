<template>
  <div 
    @click="playAudio" 
    class="flex items-center gap-2 p-2 hover:bg-stone-950 transition-color duration-150 rounded-lg group cursor-pointer"
  >
    <div class="h-full aspect-square flex items-center justify-center">
      <button 
        v-if="segmentId"
        class="flex items-center justify-center w-8 h-8 text-stone-300 group-hover:text-white group-hover:bg-stone-900 transition-color duration-150 rounded-full p-1"
        :disabled="isLoading"
        :title="isPlaying ? 'Stop' : 'Play audio'"
      >
        <Icon v-if="isLoading" name="tabler:loader" class="h-4 w-4 animate-spin" />
        <Icon v-else-if="isPlaying" name="tabler:player-stop-filled" class="h-4 w-4" />
        <Icon v-else name="tabler:player-play-filled" class="h-4 w-4" />
      </button>
    </div>
    <div class="flex flex-col items-start justify-center flex-grow">
      <div v-if="start && end" class="text-stone-400 font-mono text-xs">
        <span>{{ start }}</span>-<span>{{ end }}</span>
      </div>
      <div>
        <span class="font-medium">{{ speaker }}</span>: <span class="text-stone-200">{{ text }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useConfig } from '~/composables/useConfig';

const { baseUrl } = useConfig();

const props = defineProps({
  speaker: {
    type: String,
    required: true
  },
  text: {
    type: String,
    required: true
  },
  start: {
    type: String,
  },
  end: {
    type: String,
  },
  segmentId: {
    type: String
  }
});

const audioElement = ref(null);
const isLoading = ref(false);
const isPlaying = ref(false);

const playAudio = async () => {
  // If already playing, stop it
  if (isPlaying.value) {
    stopAudio();
    return;
  }
  
  try {
    // If we don't have an audio element yet, fetch the audio
    if (!audioElement.value) {
      isLoading.value = true;
      
      // Create an audio element
      audioElement.value = new Audio();
      
      // Add event listeners
      audioElement.value.addEventListener('ended', () => {
        isPlaying.value = false;
      });
      
      // Set the source - this will trigger the fetch
      audioElement.value.src = `http://${baseUrl.value}/segment/${props.segmentId}/audio`;
      
      // Wait for audio to be loaded
      await new Promise((resolve, reject) => {
        audioElement.value.addEventListener('canplaythrough', resolve);
        audioElement.value.addEventListener('error', reject);
        audioElement.value.load();
      });
      
      isLoading.value = false;
    }
    
    // Play the audio
    await audioElement.value.play();
    isPlaying.value = true;
  } catch (error) {
    console.error('Error playing audio:', error);
    isLoading.value = false;
    isPlaying.value = false;
  }
};

const stopAudio = () => {
  if (audioElement.value) {
    audioElement.value.pause();
    audioElement.value.currentTime = 0;
    isPlaying.value = false;
  }
};
</script>