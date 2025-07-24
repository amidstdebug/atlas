<script setup lang="ts">
import { X, HelpCircle } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface NERCategory {
  name: string
  class: string
  description: string
}

interface Props {
  isOpen: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:isOpen': [value: boolean]
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

function closeModal() {
  emit('update:isOpen', false)
}
</script>

<template>
  <!-- Modal -->
  <div
    v-if="isOpen"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
    @click.self="closeModal"
  >
    <Card class="w-full max-w-lg max-h-[80vh] overflow-hidden border-0 shadow-2xl bg-card/95 backdrop-blur-xl">
      <CardHeader class="pb-4 border-b border-border/50">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-900/30">
              <HelpCircle class="h-5 w-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <CardTitle class="text-lg">Entity Recognition Legend</CardTitle>
              <p class="text-sm text-muted-foreground">Color coding for identified entities in transcriptions</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" @click="closeModal">
            <X class="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>

      <CardContent class="p-6 overflow-y-auto max-h-[calc(80vh-120px)]">
        <div class="space-y-4">
          <div 
            v-for="category in nerCategories" 
            :key="category.name"
            class="flex items-start space-x-3 p-3 rounded-lg bg-muted/30 border border-border/50"
          >
            <span 
              :class="category.class"
              class="inline-block px-3 py-1.5 text-xs font-medium rounded flex-shrink-0"
            >
              {{ category.name }}
            </span>
            <div class="flex-1 min-w-0">
              <h4 class="text-sm font-medium text-foreground mb-1">{{ category.name }}</h4>
              <p class="text-xs text-muted-foreground">{{ category.description }}</p>
            </div>
          </div>
        </div>

        <!-- Usage Instructions -->
        <div class="mt-6 p-4 rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800">
          <h4 class="text-sm font-medium text-blue-900 dark:text-blue-100 mb-2">How to Use</h4>
          <ul class="text-xs text-blue-700 dark:text-blue-300 space-y-1">
            <li>• Entities are automatically highlighted as transcription is processed</li>
            <li>• Colors help quickly identify different types of information</li>
            <li>• Click on highlighted text to see entity details</li>
            <li>• Use this legend to understand the color coding system</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  </div>
</template>

<style scoped>
/* NER Entity Highlighting Styles for Legend */
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
  background-color: rgba(16, 185, 129, 0.15);
  color: #047857;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.ner-location {
  background-color: rgba(139, 92, 246, 0.15);
  color: #6d28d9;
  border: 1px solid rgba(139, 92, 246, 0.3);
}

.ner-impact {
  background-color: rgba(239, 68, 68, 0.15);
  color: #dc2626;
  border: 1px solid rgba(239, 68, 68, 0.3);
}
</style> 