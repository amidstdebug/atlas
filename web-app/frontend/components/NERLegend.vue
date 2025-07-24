<script setup lang="ts">
import { HelpCircle } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

interface NERCategory {
  name: string
  class: string
  description: string
}

const emit = defineEmits<{
  'open-ner-legend': []
}>()

const nerCategories: NERCategory[] = [
  { 
    name: 'IDENTIFIER', 
    class: 'ner-identifier',
    description: 'Aircraft callsigns, controller names, and identification codes'
  },
  { 
    name: 'WEATHER', 
    class: 'ner-weather',
    description: 'Weather conditions, visibility, wind information'
  },
  { 
    name: 'TIMES', 
    class: 'ner-times',
    description: 'Time references, schedules, and temporal information'
  },
  { 
    name: 'LOCATION', 
    class: 'ner-location',
    description: 'Positions, runways, waypoints, and geographic references'
  },
  { 
    name: 'IMPACT', 
    class: 'ner-impact',
    description: 'Emergencies, deviations, incidents, and critical events'
  }
]

function handleClick() {
  emit('open-ner-legend')
}

// Export nerCategories for use by parent components
defineExpose({ nerCategories })
</script>

<template>
  <Button
    variant="outline"
    size="sm"
    @click="handleClick"
    class="text-xs font-medium"
  >
    <HelpCircle class="w-3 h-3 mr-1.5" />
    Entity Legend
  </Button>
</template>

<style scoped>
/* Apply the same NER highlighting styles */
.ner-identifier {
  background-color: rgba(250, 204, 21, 0.2);
  color: #a16207;
  border: 1px solid rgba(250, 204, 21, 0.4);
}

.ner-weather {
  background-color: rgba(59, 130, 246, 0.15);
  color: #1d4ed8;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.ner-times {
  background-color: rgba(168, 85, 247, 0.15);
  color: #7e22ce;
  border: 1px solid rgba(168, 85, 247, 0.3);
}

.ner-location {
  background-color: rgba(34, 197, 94, 0.15);
  color: #15803d;
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.ner-impact {
  background-color: rgba(239, 68, 68, 0.15);
  color: #dc2626;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

/* Dark mode variants */
.dark .ner-identifier {
  background-color: rgba(250, 204, 21, 0.15);
  color: #facc15;
  border-color: rgba(250, 204, 21, 0.3);
}

.dark .ner-weather {
  background-color: rgba(59, 130, 246, 0.15);
  color: #93c5fd;
  border-color: rgba(59, 130, 246, 0.3);
}

.dark .ner-times {
  background-color: rgba(168, 85, 247, 0.15);
  color: #c084fc;
  border-color: rgba(168, 85, 247, 0.3);
}

.dark .ner-location {
  background-color: rgba(34, 197, 94, 0.15);
  color: #4ade80;
  border-color: rgba(34, 197, 94, 0.3);
}

.dark .ner-impact {
  background-color: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.3);
}
</style>