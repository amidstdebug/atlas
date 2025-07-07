<script setup lang="ts">
import { Sparkles, Clock, AlertTriangle, Users, TrendingUp, Settings, Plus, Flag, Eye } from 'lucide-vue-next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'

interface Summary {
  id: string
  summary: string
  timestamp: string
  structured_summary?: {
    situation_update: string
    current_situation_details: string
    recent_actions_taken: string
    overall_status: string
  }
}

interface AlertRule {
  id: string
  keywords: string[]
  description: string
  severity: 'low' | 'medium' | 'high'
  active: boolean
}

interface AlertItem {
  id: string
  rule: AlertRule
  timestamp: string
  context: string
  severity: 'low' | 'medium' | 'high'
}

interface Props {
  summaries: Summary[]
  isGenerating: boolean
  autoReportEnabled: boolean
  nextReportCountdown: number
  formatSummaryContent: (content: string) => string
  transcriptionSegments: any[]
  aggregatedTranscription: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'forceAnalysis'): void
  (e: 'toggleAutoMode'): void
}>()

// Mode state
const isAutoMode = ref(props.autoReportEnabled)
watch(() => props.autoReportEnabled, (newVal) => {
  isAutoMode.value = newVal
})

// Alert management
const alertRules = ref<AlertRule[]>([
  {
    id: '1',
    keywords: ['emergency', 'mayday', 'urgent'],
    description: 'Emergency situations requiring immediate attention',
    severity: 'high',
    active: true
  },
  {
    id: '2',
    keywords: ['weather', 'turbulence', 'storm'],
    description: 'Weather-related incidents',
    severity: 'medium',
    active: true
  }
])

const activeAlerts = ref<AlertItem[]>([])
const isAlertDialogOpen = ref(false)
const newAlertKeywords = ref('')
const newAlertDescription = ref('')
const newAlertSeverity = ref<'low' | 'medium' | 'high'>('medium')

// Get latest structured summary
const latestStructuredSummary = computed(() => {
  const latest = props.summaries[props.summaries.length - 1]
  return latest?.structured_summary
})

function formatTimestampBadge(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

function getSectionTimestamps(section: any) {
  if (!section?.timestamps || !Array.isArray(section.timestamps)) {
    return []
  }
  return section.timestamps.slice(0, 5)
}

function handleToggleAutoMode() {
  isAutoMode.value = !isAutoMode.value
  emit('toggleAutoMode')
}

function handleForceAnalysis() {
  emit('forceAnalysis')
}

function addAlertRule() {
  if (!newAlertKeywords.value.trim() || !newAlertDescription.value.trim()) return
  
  const newRule: AlertRule = {
    id: Date.now().toString(),
    keywords: newAlertKeywords.value.split(',').map(k => k.trim()),
    description: newAlertDescription.value,
    severity: newAlertSeverity.value,
    active: true
  }
  
  alertRules.value.push(newRule)
  
  // Reset form
  newAlertKeywords.value = ''
  newAlertDescription.value = ''
  newAlertSeverity.value = 'medium'
  isAlertDialogOpen.value = false
}

function removeAlertRule(id: string) {
  alertRules.value = alertRules.value.filter(rule => rule.id !== id)
}

function toggleAlertRule(id: string) {
  const rule = alertRules.value.find(r => r.id === id)
  if (rule) {
    rule.active = !rule.active
  }
}

// Monitor transcription for alert keywords
watch(() => props.aggregatedTranscription, (newTranscription) => {
  if (!newTranscription) return
  
  const recentText = newTranscription.toLowerCase()
  
  alertRules.value.forEach(rule => {
    if (!rule.active) return
    
    rule.keywords.forEach(keyword => {
      if (recentText.includes(keyword.toLowerCase())) {
        // Check if we already have this alert recently
        const existingAlert = activeAlerts.value.find(alert => 
          alert.rule.id === rule.id && 
          Date.now() - new Date(alert.timestamp).getTime() < 300000 // 5 minutes
        )
        
        if (!existingAlert) {
          const newAlert: AlertItem = {
            id: Date.now().toString(),
            rule: rule,
            timestamp: new Date().toISOString(),
            context: recentText.slice(Math.max(0, recentText.indexOf(keyword.toLowerCase()) - 50), recentText.indexOf(keyword.toLowerCase()) + 50),
            severity: rule.severity
          }
          activeAlerts.value.push(newAlert)
        }
      }
    })
  })
}, { deep: true })

function dismissAlert(id: string) {
  activeAlerts.value = activeAlerts.value.filter(alert => alert.id !== id)
}

const severityConfig = {
  high: { color: 'text-red-600', bgColor: 'bg-red-50', borderColor: 'border-red-200' },
  medium: { color: 'text-orange-600', bgColor: 'bg-orange-50', borderColor: 'border-orange-200' },
  low: { color: 'text-blue-600', bgColor: 'bg-blue-50', borderColor: 'border-blue-200' }
}
</script>

<template>
  <Card class="h-full flex flex-col border-0 shadow-none bg-background">
    <CardHeader class="pb-2 border-b border-border">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-900/30">
            <Sparkles class="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div>
            <CardTitle class="text-lg">Live Incident Analysis</CardTitle>
            <p class="text-sm text-muted-foreground">Real-time AI-powered analysis</p>
          </div>
        </div>
        <div class="flex items-center space-x-3">
          <div class="flex items-center space-x-2">
            <Eye class="h-4 w-4 text-muted-foreground" />
            <span class="text-sm text-muted-foreground">Manual</span>
            <Switch 
              :checked="isAutoMode" 
              @update:checked="handleToggleAutoMode"
            />
            <span class="text-sm text-muted-foreground">Auto</span>
          </div>
          <Button
            v-if="!isAutoMode"
            @click="handleForceAnalysis"
            :disabled="isGenerating"
            variant="outline"
            size="sm"
            class="text-xs"
          >
            <Sparkles class="h-3 w-3 mr-1" />
            {{ isGenerating ? 'Analyzing...' : 'Generate Analysis' }}
          </Button>
          <div v-else class="flex items-center space-x-1 px-2 py-1 rounded-md bg-muted/20 border border-border/40">
            <div class="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"></div>
            <span class="text-xs text-muted-foreground">Auto</span>
            <span v-if="nextReportCountdown > 0" class="text-xs text-muted-foreground/60">{{ nextReportCountdown }}s</span>
          </div>
        </div>
      </div>
    </CardHeader>
    
    <CardContent class="flex-1 overflow-hidden p-0">
      <div v-if="summaries.length === 0" class="h-full flex items-center justify-center p-8">
        <div class="text-center space-y-4">
          <div class="w-16 h-16 mx-auto rounded-full bg-gradient-to-br from-indigo-100 to-purple-100 dark:from-indigo-900/30 dark:to-purple-900/30 flex items-center justify-center">
            <Sparkles class="h-8 w-8 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div class="space-y-2">
            <p class="text-muted-foreground max-w-sm">
              AI analysis will appear here as audio is processed
            </p>
            <div v-if="isAutoMode" class="flex items-center justify-center space-x-2 px-3 py-2 rounded-md bg-muted/30 border border-border/50">
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
              <span class="text-sm text-muted-foreground">
                <template v-if="nextReportCountdown > 0">
                  Next auto report in {{ nextReportCountdown }}s
                </template>
                <template v-else>
                  Auto reports ready - waiting for transcription updates
                </template>
              </span>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Kanban-style columns -->
      <div v-else class="h-full grid grid-cols-4 gap-0">
        <!-- Situation Update Column -->
        <div class="border-r border-border h-full flex flex-col">
          <div class="p-3 bg-blue-50 dark:bg-blue-900/20 border-b border-blue-200 dark:border-blue-800">
            <div class="flex items-center space-x-2">
              <AlertTriangle class="h-4 w-4 text-blue-600 dark:text-blue-400" />
              <h3 class="text-sm font-semibold text-blue-900 dark:text-blue-100">Situation Update</h3>
            </div>
            <div v-if="latestStructuredSummary?.situation_update?.latest_timestamp" class="mt-1">
              <Badge variant="outline" class="text-xs font-mono border-blue-300 text-blue-700 dark:border-blue-700 dark:text-blue-300">
                {{ formatTimestampBadge(latestStructuredSummary.situation_update.latest_timestamp) }}
              </Badge>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto p-3">
            <div v-if="latestStructuredSummary?.situation_update" 
                 v-html="formatSummaryContent(latestStructuredSummary.situation_update?.content || latestStructuredSummary.situation_update)" 
                 class="prose prose-sm max-w-none dark:prose-invert text-blue-800 dark:text-blue-200 text-xs"></div>
            <div v-else class="text-xs text-muted-foreground italic">No situation updates available</div>
          </div>
        </div>

        <!-- Current Situation Details Column -->
        <div class="border-r border-border h-full flex flex-col">
          <div class="p-3 bg-green-50 dark:bg-green-900/20 border-b border-green-200 dark:border-green-800">
            <div class="flex items-center space-x-2">
              <Users class="h-4 w-4 text-green-600 dark:text-green-400" />
              <h3 class="text-sm font-semibold text-green-900 dark:text-green-100">Current Details</h3>
            </div>
            <div v-if="latestStructuredSummary?.current_situation_details?.latest_timestamp" class="mt-1">
              <Badge variant="outline" class="text-xs font-mono border-green-300 text-green-700 dark:border-green-700 dark:text-green-300">
                {{ formatTimestampBadge(latestStructuredSummary.current_situation_details.latest_timestamp) }}
              </Badge>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto p-3">
            <div v-if="latestStructuredSummary?.current_situation_details" 
                 v-html="formatSummaryContent(latestStructuredSummary.current_situation_details?.content || latestStructuredSummary.current_situation_details)" 
                 class="prose prose-sm max-w-none dark:prose-invert text-green-800 dark:text-green-200 text-xs"></div>
            <div v-else class="text-xs text-muted-foreground italic">No current details available</div>
          </div>
        </div>

        <!-- Recent Actions Column -->
        <div class="border-r border-border h-full flex flex-col">
          <div class="p-3 bg-orange-50 dark:bg-orange-900/20 border-b border-orange-200 dark:border-orange-800">
            <div class="flex items-center space-x-2">
              <Clock class="h-4 w-4 text-orange-600 dark:text-orange-400" />
              <h3 class="text-sm font-semibold text-orange-900 dark:text-orange-100">Recent Actions</h3>
            </div>
            <div v-if="latestStructuredSummary?.recent_actions_taken?.latest_timestamp" class="mt-1">
              <Badge variant="outline" class="text-xs font-mono border-orange-300 text-orange-700 dark:border-orange-700 dark:text-orange-300">
                {{ formatTimestampBadge(latestStructuredSummary.recent_actions_taken.latest_timestamp) }}
              </Badge>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto p-3">
            <div v-if="latestStructuredSummary?.recent_actions_taken" 
                 v-html="formatSummaryContent(latestStructuredSummary.recent_actions_taken?.content || latestStructuredSummary.recent_actions_taken)" 
                 class="prose prose-sm max-w-none dark:prose-invert text-orange-800 dark:text-orange-200 text-xs"></div>
            <div v-else class="text-xs text-muted-foreground italic">No recent actions available</div>
          </div>
        </div>

        <!-- Alerts/Flags Column -->
        <div class="h-full flex flex-col">
          <div class="p-3 bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-800">
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-2">
                <Flag class="h-4 w-4 text-red-600 dark:text-red-400" />
                <h3 class="text-sm font-semibold text-red-900 dark:text-red-100">Alerts</h3>
              </div>
              <Dialog v-model:open="isAlertDialogOpen">
                <DialogTrigger asChild>
                  <Button size="sm" variant="outline" class="h-6 w-6 p-0">
                    <Plus class="h-3 w-3" />
                  </Button>
                </DialogTrigger>
                <DialogContent class="sm:max-w-[425px]">
                  <DialogHeader>
                    <DialogTitle>Add Alert Rule</DialogTitle>
                  </DialogHeader>
                  <div class="space-y-4 py-4">
                    <div class="space-y-2">
                      <label class="text-sm font-medium">Keywords (comma-separated)</label>
                      <Input
                        v-model="newAlertKeywords"
                        placeholder="e.g., emergency, mayday, urgent"
                      />
                    </div>
                    <div class="space-y-2">
                      <label class="text-sm font-medium">Description</label>
                      <Textarea
                        v-model="newAlertDescription"
                        placeholder="Describe what this alert monitors"
                        rows="3"
                      />
                    </div>
                    <div class="space-y-2">
                      <label class="text-sm font-medium">Severity</label>
                      <select v-model="newAlertSeverity" class="w-full px-3 py-2 border rounded-md">
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                      </select>
                    </div>
                    <div class="flex justify-end space-x-2">
                      <Button @click="isAlertDialogOpen = false" variant="outline">Cancel</Button>
                      <Button @click="addAlertRule">Add Rule</Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto p-3 space-y-2">
            <!-- Active Alerts -->
            <div v-if="activeAlerts.length > 0" class="space-y-2">
              <div
                v-for="alert in activeAlerts"
                :key="alert.id"
                :class="[
                  'p-2 rounded-md border text-xs',
                  severityConfig[alert.severity].bgColor,
                  severityConfig[alert.severity].borderColor
                ]"
              >
                <div class="flex items-center justify-between mb-1">
                  <Badge :class="severityConfig[alert.severity].color" variant="secondary" class="text-xs">
                    {{ alert.severity.toUpperCase() }}
                  </Badge>
                  <Button @click="dismissAlert(alert.id)" size="sm" variant="ghost" class="h-4 w-4 p-0">
                    ×
                  </Button>
                </div>
                <div class="font-medium mb-1">{{ alert.rule.description }}</div>
                <div class="text-muted-foreground">{{ alert.context }}</div>
              </div>
            </div>
            
            <!-- Alert Rules Management -->
            <div class="space-y-2 border-t pt-2">
              <div class="text-xs font-medium text-muted-foreground">Alert Rules</div>
              <div v-if="alertRules.length === 0" class="text-xs text-muted-foreground italic">No alert rules configured</div>
              <div v-else class="space-y-1">
                <div
                  v-for="rule in alertRules"
                  :key="rule.id"
                  class="flex items-center justify-between p-2 rounded-md bg-muted/20 border"
                >
                  <div class="flex-1 text-xs">
                    <div class="font-medium">{{ rule.description }}</div>
                    <div class="text-muted-foreground">{{ rule.keywords.join(', ') }}</div>
                  </div>
                  <div class="flex items-center space-x-1">
                    <Button
                      @click="toggleAlertRule(rule.id)"
                      :variant="rule.active ? 'default' : 'outline'"
                      size="sm"
                      class="h-6 w-6 p-0"
                    >
                      <Eye class="h-3 w-3" />
                    </Button>
                    <Button
                      @click="removeAlertRule(rule.id)"
                      size="sm"
                      variant="ghost"
                      class="h-6 w-6 p-0 text-red-500"
                    >
                      ×
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>