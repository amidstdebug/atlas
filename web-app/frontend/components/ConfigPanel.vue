<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { X, Settings, RotateCcw } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'

interface Props {
  isOpen: boolean
  customPrompt: string
  replaceNumbers: boolean
  useIcaoCallsigns: boolean
  autoReportEnabled: boolean
  autoReportInterval: number
}

interface Emits {
  (e: 'update:isOpen', value: boolean): void
  (e: 'update:customPrompt', value: string): void
  (e: 'update:replaceNumbers', value: boolean): void
  (e: 'update:useIcaoCallsigns', value: boolean): void
  (e: 'update:autoReportEnabled', value: boolean): void
  (e: 'update:autoReportInterval', value: number): void
  (e: 'reset'): void
  (e: 'apply'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const defaultPrompt = `You are an expert Air Traffic Control incident analyst. You will be provided with ATC transmission transcripts and optionally a previous incident report.

**CRITICAL: Your response must be a structured text report, NOT JSON, NOT an array, NOT code blocks.**

**PREVIOUS REPORT CONTEXT:**
{PREVIOUS_SUMMARY}

**TEMPLATE VARIABLE INFO:** The {PREVIOUS_SUMMARY} variable above will be automatically replaced with the previous incident report if one exists, or with "No previous report available" for the first analysis. You can use this variable in custom prompts to access previous report context.

Your task:
1. Analyze the new ATC transcript for any issues, incidents, or noteworthy events
2. Compare with the previous report (if provided) to identify what has changed
3. Correct any obvious transcription errors (wrong frequencies, callsigns, etc.)
4. Provide an updated incident analysis report that tracks the evolving situation

**OUTPUT FORMAT - Return your response in this exact structure:**

**INCIDENT ANALYSIS REPORT - [TIMESTAMP]**

**Aircraft Callsign:** [Primary aircraft involved]
**Event Summary:** [Brief description of what happened]
**Current Location:** [Latest position, runway, airspace, etc.]

**Situation Update:**
• [What has changed since the last report - NEW DEVELOPMENTS]
• [Current status vs previous status - CHANGES IN SITUATION]
• [Any progression or resolution of issues - EVOLUTION]

**Current Situation Details:**
• [Key factual detail 1 - current state]
• [Key factual detail 2 - current state]
• [Additional current details as needed]

**Recent Actions Taken:**
• [New action 1 with specifics since last report]
• [New action 2 with specifics since last report]
• [Additional recent actions as needed]

**Overall Status:** [Current state - improved/worsened/unchanged from previous report]

**Change Summary:** [Brief summary of what has changed since the previous report, or "No significant changes" if applicable]

**IMPORTANT RULES:**
- Focus on CHANGES and UPDATES since the previous report
- If this is the first report (no previous report), focus on current situation
- Always include a "Situation Update" section highlighting what's new or different
- Be specific about what has changed vs what remains the same
- Include timestamps, frequencies, headings, altitudes, distances with changes
- Use plain text formatting with bullet points and headings as shown above
- Do not use JSON, code blocks, or array formatting
- Write as a professional ATC incident report focused on tracking situation evolution`

const localCustomPrompt = ref(props.customPrompt)
const localReplaceNumbers = ref(props.replaceNumbers)
const localUseIcaoCallsigns = ref(props.useIcaoCallsigns)
const localAutoReportEnabled = ref(props.autoReportEnabled)
const localAutoReportInterval = ref(props.autoReportInterval)

// Watch for prop changes and sync local state
watch(() => props.customPrompt, (newVal) => {
  localCustomPrompt.value = newVal
})

watch(() => props.replaceNumbers, (newVal) => {
  localReplaceNumbers.value = newVal
})

watch(() => props.useIcaoCallsigns, (newVal) => {
  localUseIcaoCallsigns.value = newVal
})

watch(() => props.autoReportEnabled, (newVal) => {
  localAutoReportEnabled.value = newVal
})

watch(() => props.autoReportInterval, (newVal) => {
  localAutoReportInterval.value = newVal
})

const hasCustomChanges = computed(() => {
  return localCustomPrompt.value !== '' ||
         !localReplaceNumbers.value ||
         !localUseIcaoCallsigns.value ||
         localAutoReportEnabled.value ||
         localAutoReportInterval.value !== 30
})

function closePanel() {
  emit('update:isOpen', false)
}

function applyChanges() {
  emit('update:customPrompt', localCustomPrompt.value)
  emit('update:replaceNumbers', localReplaceNumbers.value)
  emit('update:useIcaoCallsigns', localUseIcaoCallsigns.value)
  emit('update:autoReportEnabled', localAutoReportEnabled.value)
  emit('update:autoReportInterval', localAutoReportInterval.value)
  emit('apply') // Emit apply event for toast handling
  closePanel()
}

function resetToDefaults() {
  localCustomPrompt.value = ''
  localReplaceNumbers.value = true
  localUseIcaoCallsigns.value = true
  localAutoReportEnabled.value = false
  localAutoReportInterval.value = 30
  emit('reset')
}

function loadDefaultPrompt() {
  localCustomPrompt.value = defaultPrompt
}
</script>

<template>
  <div
    v-if="isOpen"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
    @click.self="closePanel"
  >
    <Card class="w-full max-w-2xl max-h-[80vh] overflow-hidden border-0 shadow-2xl bg-card/95 backdrop-blur-xl">
      <CardHeader class="pb-4 border-b border-border/50">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30">
              <Settings class="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <CardTitle class="text-lg">Analysis Configuration</CardTitle>
              <p class="text-sm text-muted-foreground">Customize transcription processing and AI instructions</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" @click="closePanel">
            <X class="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>

      <CardContent class="p-6 space-y-6 overflow-y-auto max-h-[60vh]">
        <!-- Transcription Processing Options -->
        <div class="space-y-4">
          <div>
            <h3 class="font-semibold text-sm text-foreground mb-3">Transcription Processing</h3>
            <p class="text-xs text-muted-foreground mb-4">These options modify the transcription text before analysis</p>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <!-- Replace Numbers Toggle -->
            <div class="flex items-center justify-between p-4 rounded-lg bg-muted/30 border border-border/50">
              <div class="space-y-1">
                <Label class="text-sm font-medium">Replace Numbers</Label>
                <p class="text-xs text-muted-foreground">Convert spoken numbers to digits<br>("twenty three" → "23")</p>
              </div>
              <button
                @click="localReplaceNumbers = !localReplaceNumbers"
                class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                :class="localReplaceNumbers ? 'bg-blue-500' : 'bg-gray-200 dark:bg-gray-700'"
              >
                <span
                  class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                  :class="localReplaceNumbers ? 'translate-x-6' : 'translate-x-1'"
                />
              </button>
            </div>

            <!-- ICAO Callsigns Toggle -->
            <div class="flex items-center justify-between p-4 rounded-lg bg-muted/30 border border-border/50">
              <div class="space-y-1">
                <Label class="text-sm font-medium">ICAO Callsigns</Label>
                <p class="text-xs text-muted-foreground">Convert airline names to ICAO codes<br>("American 123" → "AAL123")</p>
              </div>
              <button
                @click="localUseIcaoCallsigns = !localUseIcaoCallsigns"
                class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                :class="localUseIcaoCallsigns ? 'bg-blue-500' : 'bg-gray-200 dark:bg-gray-700'"
              >
                <span
                  class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                  :class="localUseIcaoCallsigns ? 'translate-x-6' : 'translate-x-1'"
                />
              </button>
            </div>
          </div>
        </div>

        <!-- Auto Report Settings -->
        <div class="space-y-4">
          <div>
            <h3 class="font-semibold text-sm text-foreground mb-3">Auto Report Settings</h3>
            <p class="text-xs text-muted-foreground mb-4">Configure automatic incident report generation</p>
          </div>

          <div class="space-y-4">
            <!-- Auto Report Toggle -->
            <div class="flex items-center justify-between p-4 rounded-lg bg-muted/30 border border-border/50">
              <div class="space-y-1">
                <Label class="text-sm font-medium">Auto Report</Label>
                <p class="text-xs text-muted-foreground">Generate reports automatically when<br>transcription updates</p>
              </div>
              <button
                @click="localAutoReportEnabled = !localAutoReportEnabled"
                class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                :class="localAutoReportEnabled ? 'bg-blue-500' : 'bg-gray-200 dark:bg-gray-700'"
              >
                <span
                  class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                  :class="localAutoReportEnabled ? 'translate-x-6' : 'translate-x-1'"
                />
              </button>
            </div>

            <!-- Minimum Interval Setting -->
            <div class="p-4 rounded-lg bg-muted/30 border border-border/50">
              <div class="space-y-3">
                <div class="flex items-center justify-between">
                  <Label class="text-sm font-medium">Minimum Interval</Label>
                  <span class="text-xs text-muted-foreground">{{ localAutoReportInterval }} seconds</span>
                </div>
                <p class="text-xs text-muted-foreground">Minimum time between automatic reports</p>
                <div class="space-y-2">
                  <Input
                    v-model.number="localAutoReportInterval"
                    type="number"
                    min="10"
                    max="300"
                    step="5"
                    class="bg-background/50 border-border/50"
                    :disabled="!localAutoReportEnabled"
                  />
                  <p class="text-xs text-muted-foreground">
                    Range: 10-300 seconds (recommended: 30-60 seconds)
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Custom AI Instructions -->
        <div class="space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-semibold text-sm text-foreground">Custom AI Instructions</h3>
              <p class="text-xs text-muted-foreground mt-1">Override the default system prompt for analysis</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              @click="loadDefaultPrompt"
              class="text-xs"
            >
              Load Default
            </Button>
          </div>

          <div class="space-y-2">
            <Label for="custom-prompt" class="text-sm">System Prompt</Label>
            <Textarea
              id="custom-prompt"
              v-model="localCustomPrompt"
              placeholder="Enter custom instructions for the AI analysis... (leave empty to use default)"
              class="min-h-[200px] resize-none bg-background/50 border-border/50"
              :class="{ 'border-blue-300 dark:border-blue-600': localCustomPrompt }"
            />
            <div class="space-y-2">
              <p class="text-xs text-muted-foreground">
                {{ localCustomPrompt ? `${localCustomPrompt.length} characters` : 'Using default prompt' }}
              </p>

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
            <Button @click="applyChanges" class="bg-blue-600 hover:bg-blue-700">
              Apply Settings
            </Button>
          </div>
        </div>
      </div>
    </Card>
  </div>
</template>