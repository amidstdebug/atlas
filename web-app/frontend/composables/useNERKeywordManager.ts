import { ref, reactive, computed, watch } from 'vue'

interface ApiResponse {
  success: boolean
  message: string
  data?: any
}

interface KeywordData {
  raw_text: string
  categories: Record<string, string>
  keywords_by_category: Record<string, string[]>
  stats: {
    total_keywords: number
    categories_used: number
    keywords_by_category: Record<string, number>
  }
}

export const useNERKeywordManager = () => {
  // State
  const categories = ref<Record<string, string>>({})
  const keywordsByCategory = ref<Record<string, string[]>>({})
  const stats = ref<any>({})
  const saving = ref(false)
  const lastSaved = ref('')
  const rawText = ref('')
  const previewMode = ref(false)

  // Computed
  const totalKeywords = computed(() => {
    return Object.values(keywordsByCategory.value).reduce((total, keywords) => total + keywords.length, 0)
  })

  const activeCategories = computed(() => {
    return Object.values(keywordsByCategory.value).filter(keywords => keywords.length > 0).length
  })

  const showSaveStatus = computed(() => {
    return saving.value || (lastSaved.value && Date.now() - new Date(lastSaved.value).getTime() < 3000)
  })

  // Auto-save functionality
  let saveTimeout: NodeJS.Timeout | null = null
  const debouncedSave = () => {
    if (saveTimeout) {
      clearTimeout(saveTimeout)
    }
    saveTimeout = setTimeout(() => {
      saveKeywords()
    }, 1000)
  }

  // Methods
  const loadData = async () => {
    try {
      const { $api } = useNuxtApp()
      const response = await $api.get('/api/ner-keywords/data')
      
      if (response.data.success && response.data.data) {
        const data = response.data.data as KeywordData
        categories.value = data.categories || {}
        keywordsByCategory.value = data.keywords_by_category || {}
        stats.value = data.stats || {}
        rawText.value = data.raw_text || ''
      }
    } catch (error: any) {
      console.error('Failed to load keywords data:', error)
    }
  }

  const saveKeywords = async () => {
    if (saving.value) return
    
    saving.value = true
    try {
      const { $api } = useNuxtApp()
      
      const response = await $api.post('/api/ner-keywords/update', {
        raw_text: rawText.value
      })
      
      if (response.data.success && response.data.data) {
        keywordsByCategory.value = response.data.data.keywords_by_category || {}
        stats.value = response.data.data.stats || {}
        lastSaved.value = new Date().toLocaleTimeString()
      }
    } catch (error: any) {
      console.error('Failed to save keywords:', error)
    } finally {
      saving.value = false
    }
  }

  const exportKeywords = async () => {
    try {
      const { $api } = useNuxtApp()
      const response = await $api.get('/api/ner-keywords/export')
      
      if (response.data.success && response.data.data) {
        const blob = new Blob([JSON.stringify(response.data.data, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `ner-keywords-${new Date().toISOString().split('T')[0]}.json`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      }
    } catch (error: any) {
      console.error('Failed to export keywords:', error)
    }
  }

  const importKeywords = async (event: Event) => {
    const target = event.target as HTMLInputElement
    const file = target.files?.[0]
    
    if (!file) return
    
    try {
      const { $api } = useNuxtApp()
      const formData = new FormData()
      formData.append('file', file)
      
      const response = await $api.post('/api/ner-keywords/import-file', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      
      if (response.data.success) {
        await loadData()
      }
    } catch (error: any) {
      console.error('Failed to import keywords:', error)
    } finally {
      target.value = ''
    }
  }

  const togglePreview = () => {
    previewMode.value = !previewMode.value
  }

  return {
    // State
    categories,
    keywordsByCategory,
    stats,
    saving,
    lastSaved,
    rawText,
    previewMode,
    
    // Computed
    totalKeywords,
    activeCategories,
    showSaveStatus,
    
    // Methods
    loadData,
    saveKeywords,
    debouncedSave,
    exportKeywords,
    importKeywords,
    togglePreview
  }
} 