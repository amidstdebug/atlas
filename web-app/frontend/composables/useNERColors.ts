import { ref, computed, readonly } from 'vue'

// Global reactive state for NER colors
const nerColors = ref<Record<string, string>>({
  identifier: '#facc15',
  weather: '#3b82f6',
  times: '#a855f7',
  location: '#22c55e',
  impact: '#ef4444'
})

export const useNERColors = () => {
  const updateColor = (category: string, color: string) => {
    nerColors.value[category] = color
  }

  const getColor = (category: string) => {
    return nerColors.value[category] || nerColors.value.identifier
  }

  const getCSSVariables = computed(() => {
    const vars: Record<string, string> = {}
    Object.entries(nerColors.value).forEach(([category, color]) => {
      vars[`--ner-${category}-color`] = color
      vars[`--ner-${category}-bg`] = hexToRgba(color, 0.15)
      vars[`--ner-${category}-border`] = hexToRgba(color, 0.3)
    })
    return vars
  })

  const hexToRgba = (hex: string, alpha: number) => {
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    const b = parseInt(hex.slice(5, 7), 16)
    return `rgba(${r}, ${g}, ${b}, ${alpha})`
  }

  const loadColors = async () => {
    try {
      const response = await fetch('/api/ner-keywords/colors')
      const data = await response.json()
      if (data.success) {
        nerColors.value = { ...nerColors.value, ...data.data.colors }
      }
    } catch (error) {
      console.error('Failed to load NER colors:', error)
    }
  }

  const saveColors = async () => {
    try {
      await fetch('/api/ner-keywords/colors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ colors: nerColors.value })
      })
    } catch (error) {
      console.error('Failed to save NER colors:', error)
    }
  }

  return {
    nerColors: readonly(nerColors),
    updateColor,
    getColor,
    getCSSVariables,
    hexToRgba,
    loadColors,
    saveColors
  }
} 