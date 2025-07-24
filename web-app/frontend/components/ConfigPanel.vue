<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { X, Settings, RotateCcw, MessageSquare, Tag, Code } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'

interface Props {
  isOpen: boolean
  customSummaryPrompt: string
  customNerPrompt: string
  customFormatTemplate: string
}

interface Emits {
  (e: 'update:isOpen', value: boolean): void
  (e: 'update:customSummaryPrompt', value: string): void
  (e: 'update:customNerPrompt', value: string): void
  (e: 'update:customFormatTemplate', value: string): void
  (e: 'reset'): void
  (e: 'apply'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const defaultSummaryPrompt = `ATC incident analyst. Analyze transcripts for issues, incidents, and noteworthy events.

Compare with previous report (if provided) to identify changes. Correct transcription errors.

**PREVIOUS REPORT:**
{PREVIOUS_SUMMARY}

**OUTPUT FORMAT:**

**INCIDENT REPORT - [TIMESTAMP]**

**Aircraft:** [Primary callsign]
**Event:** [Brief description]
**Location:** [Current position]

**Updates:**
• [New developments since last report]
• [Status changes]

**Details:**
• [Key facts - current state]
• [Additional details]

**Actions:**
• [Recent actions taken]

**Status:** [Current state vs previous]
**Changes:** [Summary of changes or "No changes"]

Rules:
- Focus on CHANGES since previous report
- Include timestamps, frequencies, headings, altitudes
- Use plain text, bullet points, headings only
- No JSON or code blocks`

const defaultNerPrompt = `Clean ATC text and tag entities. Return JSON only.

Entity tags:
- IDENTIFIER: <span class="ner-identifier">callsign</span>
- WEATHER: <span class="ner-weather">weather</span> 
- TIMES: <span class="ner-times">time</span>
- LOCATION: <span class="ner-location">location</span>
- IMPACT: <span class="ner-impact">emergency</span>

Format: {"cleaned_text": "text", "ner_text": "tagged_text", "entities": []}`

// Local state for form inputs
const localCustomSummaryPrompt = ref(props.customSummaryPrompt || '')
const localCustomNerPrompt = ref(props.customNerPrompt || '')
const localCustomFormatTemplate = ref(props.customFormatTemplate || '')

// Current tab (summary, ner, or format)
const activeTab = ref<'summary' | 'ner' | 'format'>('summary')

// Watch for prop changes and sync local state
watch(() => props.customSummaryPrompt, (newVal) => {
  localCustomSummaryPrompt.value = newVal || ''
})

watch(() => props.customNerPrompt, (newVal) => {
  localCustomNerPrompt.value = newVal || ''
})

watch(() => props.customFormatTemplate, (newVal) => {
  localCustomFormatTemplate.value = newVal || ''
})

const hasCustomChanges = computed(() => {
  return localCustomSummaryPrompt.value !== '' ||
         localCustomNerPrompt.value !== '' ||
         localCustomFormatTemplate.value !== ''
})

const hasRequiredFields = computed(() => {
  return localCustomSummaryPrompt.value.trim() !== ''
})

function closePanel() {
  emit('update:isOpen', false)
}

function applyChanges() {
  if (!hasRequiredFields.value) {
    return // Don't apply if required fields are missing
  }
  
  emit('update:customSummaryPrompt', localCustomSummaryPrompt.value)
  emit('update:customNerPrompt', localCustomNerPrompt.value)
  emit('update:customFormatTemplate', localCustomFormatTemplate.value)
  emit('apply')
  closePanel()
}

function resetToDefaults() {
  localCustomSummaryPrompt.value = defaultSummaryPrompt  // Set to default instead of empty
  localCustomNerPrompt.value = ''
  localCustomFormatTemplate.value = ''
  emit('reset')
}

function loadDefaultSummaryPrompt() {
  localCustomSummaryPrompt.value = defaultSummaryPrompt
}

function loadDefaultNerPrompt() {
  localCustomNerPrompt.value = defaultNerPrompt
}

function loadDefaultFormatTemplate() {
  localCustomFormatTemplate.value = JSON.stringify({
    "pending_information": [
      {
        "description": "",
        "eta_etr_info": "",
        "calculated_time": "",
        "priority": "low|medium|high",
        "timestamps": []
      }
    ],
    "emergency_information": [
      {
        "category": "MAYDAY_PAN|CASEVAC|AIRCRAFT_DIVERSION|OTHERS",
        "description": "",
        "severity": "high",
        "immediate_action_required": true,
        "timestamps": []
      }
    ]
  }, null, 2)
}

// Validate JSON format
const isValidJson = computed(() => {
  if (!localCustomFormatTemplate.value.trim()) return true // Empty is valid (will use default)
  try {
    JSON.parse(localCustomFormatTemplate.value)
    return true
  } catch {
    return false
  }
})
</script>

<template>
  <div
    v-if="isOpen"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
    @click.self="closePanel"
  >
    <Card class="w-full max-w-4xl max-h-[85vh] overflow-hidden border-0 shadow-2xl bg-card/95 backdrop-blur-xl">
      <CardHeader class="pb-4 border-b border-border/50">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30">
              <Settings class="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <CardTitle class="text-lg">Configuration</CardTitle>
              <p class="text-sm text-muted-foreground">Customize AI prompts and processing settings</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" @click="closePanel">
            <X class="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>

      <!-- Tab Navigation -->
      <div class="border-b border-border/50 bg-muted/20">
        <div class="flex">
          <button
            @click="activeTab = 'summary'"
            class="flex items-center space-x-2 px-6 py-3 text-sm font-medium transition-colors"
            :class="activeTab === 'summary' 
              ? 'bg-background text-foreground border-b-2 border-blue-500' 
              : 'text-muted-foreground hover:text-foreground'"
          >
            <MessageSquare class="h-4 w-4" />
            <span>Summary Prompt</span>
          </button>
          <button
            @click="activeTab = 'ner'"
            class="flex items-center space-x-2 px-6 py-3 text-sm font-medium transition-colors"
            :class="activeTab === 'ner' 
              ? 'bg-background text-foreground border-b-2 border-blue-500' 
              : 'text-muted-foreground hover:text-foreground'"
          >
            <Tag class="h-4 w-4" />
            <span>NER Prompt</span>
          </button>
          <button
            @click="activeTab = 'format'"
            class="flex items-center space-x-2 px-6 py-3 text-sm font-medium transition-colors"
            :class="activeTab === 'format' 
              ? 'bg-background text-foreground border-b-2 border-blue-500' 
              : 'text-muted-foreground hover:text-foreground'"
          >
            <Code class="h-4 w-4" />
            <span>Format Template</span>
          </button>
        </div>
      </div>

      <CardContent class="p-6 space-y-6 overflow-y-auto max-h-[55vh]">
        <!-- Summary Prompt Tab -->
        <div v-if="activeTab === 'summary'" class="space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-semibold text-sm text-foreground">Summary Generation Prompt</h3>
              <p class="text-xs text-muted-foreground mt-1">
                <span class="text-red-500">*Required:</span> Instructions for AI to generate incident reports and summaries
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              @click="loadDefaultSummaryPrompt"
              class="text-xs"
            >
              Load Default
            </Button>
          </div>

          <div class="space-y-2">
            <Label for="summary-prompt" class="text-sm">System Prompt <span class="text-red-500">*</span></Label>
            <Textarea
              id="summary-prompt"
              v-model="localCustomSummaryPrompt"
              placeholder="Enter instructions for summary generation... (required field)"
              class="min-h-[300px] resize-none bg-background/50 border-border/50"
              :class="{ 
                'border-blue-300 dark:border-blue-600': localCustomSummaryPrompt,
                'border-red-300 dark:border-red-600': !localCustomSummaryPrompt.trim()
              }"
              required
            />
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <p class="text-xs text-muted-foreground">
                  {{ localCustomSummaryPrompt ? `${localCustomSummaryPrompt.length} characters` : 'Prompt required' }}
                </p>
                <div class="flex items-center space-x-1" v-if="!localCustomSummaryPrompt.trim()">
                  <div class="h-2 w-2 bg-red-500 rounded-full"></div>
                  <span class="text-xs text-red-600 dark:text-red-400">Required field</span>
                </div>
              </div>

              <!-- Template Variable Help -->
              <div class="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
                <div class="flex items-start space-x-2">
                  <div class="w-4 h-4 rounded-full bg-blue-500 flex items-center justify-center mt-0.5">
                    <span class="text-white text-xs font-bold">i</span>
                  </div>
                  <div class="space-y-1">
                    <p class="text-xs font-medium text-blue-900 dark:text-blue-100">Template Variable Available</p>
                    <p class="text-xs text-blue-700 dark:text-blue-300">
                      Use <code class="bg-blue-100 dark:bg-blue-900 px-1 rounded text-blue-800 dark:text-blue-200">{PREVIOUS_SUMMARY}</code> in your prompt to access the previous incident report for change tracking and situation monitoring.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- NER Prompt Tab -->
        <div v-if="activeTab === 'ner'" class="space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-semibold text-sm text-foreground">Named Entity Recognition Prompt</h3>
              <p class="text-xs text-muted-foreground mt-1">Customize how AI identifies and highlights entities in transcriptions</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              @click="loadDefaultNerPrompt"
              class="text-xs"
            >
              Load Default
            </Button>
          </div>

          <div class="space-y-2">
            <Label for="ner-prompt" class="text-sm">NER System Prompt</Label>
            <Textarea
              id="ner-prompt"
              v-model="localCustomNerPrompt"
              placeholder="Enter custom instructions for entity recognition... (leave empty to use default)"
              class="min-h-[250px] resize-none bg-background/50 border-border/50"
              :class="{ 'border-purple-300 dark:border-purple-600': localCustomNerPrompt }"
            />
            <div class="space-y-2">
              <p class="text-xs text-muted-foreground">
                {{ localCustomNerPrompt ? `${localCustomNerPrompt.length} characters` : 'Using default NER prompt' }}
              </p>

              <!-- NER Categories Help -->
              <div class="bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800 rounded-lg p-3">
                <div class="flex items-start space-x-2">
                  <Tag class="h-4 w-4 text-purple-600 dark:text-purple-400 mt-0.5 flex-shrink-0" />
                  <div class="space-y-1">
                    <p class="text-xs font-medium text-purple-900 dark:text-purple-100">Available Entity Categories</p>
                    <div class="text-xs text-purple-700 dark:text-purple-300 space-y-1">
                      <div><code class="bg-purple-100 dark:bg-purple-900 px-1 rounded">IDENTIFIER</code> - Aircraft callsigns, controller names</div>
                      <div><code class="bg-purple-100 dark:bg-purple-900 px-1 rounded">WEATHER</code> - Weather conditions and information</div>
                      <div><code class="bg-purple-100 dark:bg-purple-900 px-1 rounded">TIMES</code> - Time references and schedules</div>
                      <div><code class="bg-purple-100 dark:bg-purple-900 px-1 rounded">LOCATION</code> - Positions, runways, waypoints</div>
                      <div><code class="bg-purple-100 dark:bg-purple-900 px-1 rounded">IMPACT</code> - Emergencies, deviations, critical events</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Format Template Tab -->
        <div v-if="activeTab === 'format'" class="space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-semibold text-sm text-foreground">JSON Format Template</h3>
              <p class="text-xs text-muted-foreground mt-1">Customize the JSON structure for structured summary generation</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              @click="loadDefaultFormatTemplate"
              class="text-xs"
            >
              Load Default
            </Button>
          </div>

          <div class="space-y-2">
            <Label for="format-template" class="text-sm">JSON Format Template</Label>
            <Textarea
              id="format-template"
              v-model="localCustomFormatTemplate"
              placeholder="Enter custom JSON format template... (leave empty to use default)"
              class="min-h-[300px] resize-none bg-background/50 border-border/50 font-mono text-sm"
              :class="{ 
                'border-green-300 dark:border-green-600': localCustomFormatTemplate && isValidJson,
                'border-red-300 dark:border-red-600': localCustomFormatTemplate && !isValidJson
              }"
            />
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <p class="text-xs text-muted-foreground">
                  {{ localCustomFormatTemplate ? `${localCustomFormatTemplate.length} characters` : 'Using default format' }}
                </p>
                <div class="flex items-center space-x-2">
                  <div class="flex items-center space-x-1">
                    <div :class="isValidJson ? 'h-2 w-2 bg-green-500 rounded-full' : 'h-2 w-2 bg-red-500 rounded-full'"></div>
                    <span class="text-xs" :class="isValidJson ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'">
                      {{ isValidJson ? 'Valid JSON' : 'Invalid JSON' }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Format Template Help -->
              <div class="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-3">
                <div class="flex items-start space-x-2">
                  <Code class="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                  <div class="space-y-1">
                    <p class="text-xs font-medium text-green-900 dark:text-green-100">Format Template Instructions</p>
                    <div class="text-xs text-green-700 dark:text-green-300 space-y-1">
                      <p>• Define the exact JSON structure the AI should output</p>
                      <p>• Use placeholder values to show expected data types</p>
                      <p>• The AI will replace placeholders with actual analysis results</p>
                      <p>• Empty string means use the default template</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>


      </CardContent>

      <!-- Footer Actions -->
      <div class="border-t border-border/50 p-6 bg-muted/20">
        <div class="flex items-center justify-between">
          <Button
            variant="outline"
            @click="resetToDefaults"
            :disabled="!hasCustomChanges"
            class="flex items-center space-x-2"
          >
            <RotateCcw class="h-3 w-3" />
            <span>Reset to Defaults</span>
          </Button>

          <div class="flex space-x-3">
            <Button variant="outline" @click="closePanel">
              Cancel
            </Button>
            <Button 
              @click="applyChanges" 
              class="bg-blue-600 hover:bg-blue-700" 
              :disabled="!isValidJson || !hasRequiredFields"
            >
              <span v-if="!hasRequiredFields">Missing Required Fields</span>
              <span v-else>Apply Settings</span>
            </Button>
          </div>
        </div>
      </div>
    </Card>
  </div>
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