import { ref, computed } from 'vue'
import { useTranscriptionStore } from '@/stores/transcription'

export interface ActionItem {
  id: string
  type: 'critical' | 'warning' | 'advisory' | 'routine'
  title: string
  description: string
  priority: number
  timestamp: string
  context?: string
  completed?: boolean
}

export interface SuggestedActionsState {
  isGenerating: boolean
  actions: ActionItem[]
  error: string | null
}

export interface AutoActionsConfig {
  enabled: boolean
  interval: number // seconds
  triggerConditions: string[]
}

export const useSuggestedActions = () => {
  const state = ref<SuggestedActionsState>({
    isGenerating: false,
    actions: [
      {
        id: 'demo-action-1',
        type: 'critical',
        title: 'Issue ILS Approach Clearance',
        description: '<strong>[00:04:09]</strong> Vector Empire 11 to seven-mile final. Treat as ILS. Continue verbal guidance.<br><br><strong>Required Actions:</strong><br>• Instruct Empire 11: descend and maintain 2,200 feet<br>• Turn Empire 11 left to heading 310<br>• At 4.5 miles: pilot\'s discretion descent, standard rate, maintain 1,000 feet',
        priority: 9,
        timestamp: new Date(Date.now() - 300000).toISOString(), // 5 minutes ago
        context: 'Vector Empire 11 - ILS Approach Sequence',
        completed: false
      },
      {
        id: 'demo-action-2',
        type: 'warning',
        title: 'Monitor Final Approach Progress',
        description: '<strong>[00:04:32]</strong> At 4 miles, ensure aircraft remains on frequency. Current conditions: Winds 010 at 7 knots.<br><br><strong>Verification Required:</strong><br>• Confirm Empire 11 established on final approach<br>• Monitor 3-mile checkpoint notification<br>• Verify runway alignment at 1.25-mile final',
        priority: 7,
        timestamp: new Date(Date.now() - 240000).toISOString(), // 4 minutes ago
        context: 'Empire 11 Final Approach Monitoring',
        completed: false
      },
      {
        id: 'demo-action-3',
        type: 'advisory',
        title: 'Coordinate Landing Clearance',
        description: '<strong>[00:04:47]</strong> Confirm Empire 11 aligned for Runway 3L at 1.25-mile final.<br><br><strong>Position Data:</strong><br>• Coordinates: N 38°44\'00", W 90°22\'86"<br>• Distance: Runway 1 mile ahead<br>• If field in sight: Clear to land Runway 30L<br>• <strong>Caution:</strong> Aircraft appears low on approach',
        priority: 6,
        timestamp: new Date(Date.now() - 180000).toISOString(), // 3 minutes ago
        context: 'Empire 11 Landing Sequence',
        completed: false
      },
      {
        id: 'demo-action-4',
        type: 'routine',
        title: 'Update Weather Information',
        description: 'Ensure current weather conditions are communicated to approaching aircraft.<br><br><strong>Current Conditions:</strong><br>• Wind: 010 at 7 knots<br>• Visibility: Good<br>• Runway conditions: Normal<br>• Approach lighting: Operational',
        priority: 3,
        timestamp: new Date(Date.now() - 120000).toISOString(), // 2 minutes ago
        context: 'Standard Weather Update',
        completed: false
      }
    ],
    error: null
  })

  const autoActionsConfig = ref<AutoActionsConfig>({
    enabled: false,
    interval: 45, // 45 seconds default
    triggerConditions: ['critical_event', 'communication_issue', 'safety_concern']
  })

  const nextActionsCountdown = ref(0)
  let actionsTimer: NodeJS.Timeout | null = null

  const generateActions = async (
    transcriptionText: string,
    transcriptionSegments?: any[],
    previousActions?: ActionItem[],
    customPrompt?: string
  ) => {
    if (!transcriptionText.trim()) {
      state.value.error = 'No transcription text provided'
      return null
    }

    state.value.isGenerating = true
    state.value.error = null

    try {
      const { $api } = useNuxtApp()
      
      // Convert transcription segments to the format expected by the backend
      const segments = transcriptionSegments?.map(seg => ({
        text: seg.text,
        start: seg.start,
        end: seg.end
      }))

      const response = await $api.post('/actions/suggest', {
        transcription: transcriptionText,
        transcription_segments: segments || undefined,
        previous_actions: previousActions || [],
        custom_prompt: customPrompt || undefined
      })

      if (response.data?.actions) {
        // Add new actions to the existing list
        const newActions = response.data.actions.map((action: any) => ({
          ...action,
          id: action.id || Date.now().toString() + Math.random().toString(36).substr(2, 9),
          timestamp: action.timestamp || new Date().toISOString(),
          completed: false
        }))

        state.value.actions = [...state.value.actions, ...newActions]
        return response.data
      }
    } catch (error: any) {
      console.error('Actions generation error:', error)
      state.value.error = error.response?.data?.detail || 'Actions generation failed'
      throw error
    } finally {
      state.value.isGenerating = false
    }
  }

  const generateAutoActions = async () => {
    const transcriptionStore = useTranscriptionStore()
    const currentTranscription = transcriptionStore.getTranscription
    const transcriptionSegments = transcriptionStore.getSegments

    if (!currentTranscription) {
      console.warn('No transcription available for auto-actions')
      return
    }

    try {
      await generateActions(
        currentTranscription,
        transcriptionSegments,
        state.value.actions.filter(a => !a.completed)
      )
    } catch (error) {
      console.error('Auto-actions generation failed:', error)
    }
  }

  const completeAction = (actionId: string) => {
    const actionIndex = state.value.actions.findIndex(a => a.id === actionId)
    if (actionIndex !== -1) {
      state.value.actions[actionIndex].completed = true
    }
  }

  const clearCompletedActions = () => {
    state.value.actions = state.value.actions.filter(a => !a.completed)
  }

  const toggleAutoActions = () => {
    autoActionsConfig.value.enabled = !autoActionsConfig.value.enabled

    if (autoActionsConfig.value.enabled) {
      startActionsTimer()
    } else {
      stopActionsTimer()
    }
  }

  const updateAutoActionsConfig = (config: Partial<AutoActionsConfig>) => {
    const wasEnabled = autoActionsConfig.value.enabled

    autoActionsConfig.value = {
      ...autoActionsConfig.value,
      ...config
    }

    // Restart timer if enabled and interval changed
    if (autoActionsConfig.value.enabled) {
      if (!wasEnabled || config.interval) {
        stopActionsTimer()
        startActionsTimer()
      }
    }
  }

  const setAutoActionsInterval = (seconds: number) => {
    updateAutoActionsConfig({ interval: seconds })
  }

  const startActionsTimer = () => {
    if (actionsTimer) clearInterval(actionsTimer)

    nextActionsCountdown.value = autoActionsConfig.value.interval

    actionsTimer = setInterval(() => {
      nextActionsCountdown.value--

      if (nextActionsCountdown.value <= 0) {
        // Trigger auto-actions generation
        generateAutoActions()
        nextActionsCountdown.value = autoActionsConfig.value.interval
      }
    }, 1000)
  }

  const stopActionsTimer = () => {
    if (actionsTimer) {
      clearInterval(actionsTimer)
      actionsTimer = null
    }
    nextActionsCountdown.value = 0
  }

  const formatActionContent = (content: string) => {
    // Basic formatting for display
    if (!content) return ''
    return content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>')
  }

  const shouldTriggerActions = (transcriptionText: string, recentSegments: any[]) => {
    // Check for trigger conditions in the transcription
    const lowerText = transcriptionText.toLowerCase()
    
    const triggerKeywords = [
      'emergency', 'mayday', 'pan pan', 'urgent', 'immediate',
      'unable', 'fuel', 'weather', 'traffic', 'conflict',
      'missed approach', 'go around', 'emergency descent'
    ]

    return triggerKeywords.some(keyword => lowerText.includes(keyword))
  }

  // Cleanup on unmount
  const cleanup = () => {
    stopActionsTimer()
  }

  return {
    state: computed(() => state.value),
    autoActionsConfig: computed(() => autoActionsConfig.value),
    autoActionsEnabled: computed(() => autoActionsConfig.value.enabled),
    nextActionsCountdown: computed(() => nextActionsCountdown.value),
    actions: computed(() => state.value.actions),
    pendingActions: computed(() => state.value.actions.filter(a => !a.completed)),
    completedActions: computed(() => state.value.actions.filter(a => a.completed)),
    criticalActions: computed(() => state.value.actions.filter(a => a.type === 'critical' && !a.completed)),
    generateActions,
    generateAutoActions,
    completeAction,
    clearCompletedActions,
    toggleAutoActions,
    updateAutoActionsConfig,
    setAutoActionsInterval,
    formatActionContent,
    shouldTriggerActions,
    cleanup
  }
}